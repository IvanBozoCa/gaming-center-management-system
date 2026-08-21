using System.Diagnostics;
using System.IO.Pipes;
using System.Security.AccessControl;
using System.Security.Principal;
using System.Text;
using System.Text.Json;
using System.Threading.Channels;

using StationAgent.Contracts.Ipc;
using StationAgent.Service.Security;
using StationAgent.Service.State;

namespace StationAgent.Service.Ipc;

public sealed class StationIpcServer(
    ILogger<StationIpcServer> logger,
    StationCredentialStore credentialStore,
    StationRuntimeState runtimeState
) : BackgroundService
{
    protected override async Task ExecuteAsync(
        CancellationToken stoppingToken
    )
    {
        StationCredential? credential =
            credentialStore.Load();

        if (credential is null)
        {
            logger.LogWarning(
                "Station IPC server was not started "
                + "because the station is not enrolled."
            );

            return;
        }

        logger.LogInformation(
            "Station IPC server started. "
            + "Pipe={PipeName}",
            IpcProtocol.PipeName
        );

        while (!stoppingToken.IsCancellationRequested)
        {
            try
            {
                await RunClientSessionAsync(
                    credential,
                    stoppingToken
                );
            }
            catch (OperationCanceledException)
                when (
                    stoppingToken
                        .IsCancellationRequested
                )
            {
                break;
            }
            catch (IOException exception)
            {
                logger.LogDebug(
                    exception,
                    "Station UI disconnected "
                    + "from IPC."
                );
            }
            catch (Exception exception)
            {
                logger.LogError(
                    exception,
                    "Unexpected Station IPC error."
                );

                await Task.Delay(
                    TimeSpan.FromSeconds(1),
                    stoppingToken
                );
            }
        }

        logger.LogInformation(
            "Station IPC server stopped."
        );
    }

    private async Task RunClientSessionAsync(
    StationCredential credential,
    CancellationToken cancellationToken
)
    {
        await using NamedPipeServerStream pipe =
            CreatePipe();

        logger.LogDebug(
            "Waiting for Station UI IPC connection."
        );

        await pipe.WaitForConnectionAsync(
            cancellationToken
        );

        logger.LogInformation(
            "Station UI connected to IPC."
        );

        using StreamReader reader =
            new(
                pipe,
                new UTF8Encoding(false),
                detectEncodingFromByteOrderMarks:
                    false,
                bufferSize: 4096,
                leaveOpen: true
            );

        using StreamWriter writer =
            new(
                pipe,
                new UTF8Encoding(false),
                bufferSize: 4096,
                leaveOpen: true
            )
            {
                AutoFlush = true,
            };

        string? rawMessage =
            await reader.ReadLineAsync(
                cancellationToken
            );

        if (rawMessage is null)
        {
            return;
        }

        UiHelloMessage? hello;

        try
        {
            hello =
                JsonSerializer.Deserialize<
                    UiHelloMessage
                >(
                    rawMessage,
                    IpcProtocol.JsonOptions
                );
        }
        catch (JsonException)
        {
            await SendErrorAsync(
                writer,
                correlationId: null,
                code: "INVALID_JSON",
                message:
                    "Invalid IPC JSON message."
            );

            return;
        }

        if (
            hello is null
            || hello.Version
                != IpcProtocol.Version
            || hello.Type
                != IpcProtocol.HelloType
            || hello.EventId
                == Guid.Empty
            || hello.UiInstanceId
                == Guid.Empty
            || hello.ProcessId <= 0
        )
        {
            await SendErrorAsync(
                writer,
                correlationId:
                    hello?.EventId,
                code: "INVALID_HELLO",
                message:
                    "Invalid UI HELLO message."
            );

            return;
        }

        uint actualProcessId =
            NamedPipeClientIdentity
                .GetClientProcessId(
                    pipe.SafePipeHandle
                );

        if (
            actualProcessId
                != (uint)hello.ProcessId
        )
        {
            logger.LogWarning(
                "Rejected Station UI IPC client. "
                + "DeclaredProcessId="
                + "{DeclaredProcessId} "
                + "ActualProcessId="
                + "{ActualProcessId}",
                hello.ProcessId,
                actualProcessId
            );

            await SendErrorAsync(
                writer,
                correlationId:
                    hello.EventId,
                code:
                    "CLIENT_IDENTITY_MISMATCH",
                message:
                    "IPC client identity mismatch."
            );

            return;
        }

        using Process clientProcess =
            Process.GetProcessById(
                checked(
                    (int)actualProcessId
                )
            );

        if (clientProcess.SessionId == 0)
        {
            logger.LogWarning(
                "Rejected Station UI IPC client "
                + "from Session 0. "
                + "ProcessId={ProcessId}",
                actualProcessId
            );

            await SendErrorAsync(
                writer,
                correlationId:
                    hello.EventId,
                code:
                    "NON_INTERACTIVE_CLIENT",
                message:
                    "IPC client must run "
                    + "in an interactive "
                    + "Windows session."
            );

            return;
        }

        ServiceWelcomeMessage welcome =
            new(
                IpcProtocol.Version,
                IpcProtocol.WelcomeType,
                Guid.NewGuid(),
                hello.EventId,
                DateTimeOffset.UtcNow,
                credential.StationId,
                credential.StationCode
            );

        string serializedWelcome =
            JsonSerializer.Serialize(
                welcome,
                IpcProtocol.JsonOptions
            );

        await writer.WriteLineAsync(
            serializedWelcome
        );

        Channel<StationRuntimeSnapshot>
            stateChannel =
                Channel.CreateUnbounded<
                    StationRuntimeSnapshot
                >(
                    new UnboundedChannelOptions
                    {
                        SingleReader = true,
                        SingleWriter = false,
                    }
                );

        void OnRuntimeStateChanged(
            StationRuntimeSnapshot snapshot
        )
        {
            stateChannel.Writer.TryWrite(
                snapshot
            );
        }

        runtimeState.Changed +=
            OnRuntimeStateChanged;

        try
        {
            StationRuntimeSnapshot snapshot =
                runtimeState.GetSnapshot();

            await SendStateAsync(
                writer,
                credential,
                snapshot,
                welcome.EventId
            );

            logger.LogInformation(
                "Station UI IPC handshake completed. "
                + "UiInstanceId={UiInstanceId} "
                + "ProcessId={ProcessId} "
                + "SessionId={SessionId}",
                hello.UiInstanceId,
                actualProcessId,
                clientProcess.SessionId
            );

            using CancellationTokenSource
                sessionCancellation =
                    CancellationTokenSource
                        .CreateLinkedTokenSource(
                            cancellationToken
                        );

            Task receiveTask =
                ReceiveClientMessagesAsync(
                    reader,
                    sessionCancellation.Token
                );

            Task stateTask =
                SendStateUpdatesAsync(
                    writer,
                    credential,
                    welcome.EventId,
                    stateChannel.Reader,
                    sessionCancellation.Token
                );

            await Task.WhenAny(
                receiveTask,
                stateTask
            );

            sessionCancellation.Cancel();

            stateChannel.Writer.TryComplete();

            try
            {
                await Task.WhenAll(
                    receiveTask,
                    stateTask
                );
            }
            catch (OperationCanceledException)
            {
                // Normal IPC session shutdown.
            }
        }
        finally
        {
            runtimeState.Changed -=
                OnRuntimeStateChanged;

            stateChannel.Writer.TryComplete();
        }

        logger.LogInformation(
            "Station UI disconnected from IPC."
        );
    }

    private static async Task
    ReceiveClientMessagesAsync(
        StreamReader reader,
        CancellationToken cancellationToken
    )
    {
        while (
            !cancellationToken
                .IsCancellationRequested
        )
        {
            string? message =
                await reader.ReadLineAsync(
                    cancellationToken
                );

            if (message is null)
            {
                return;
            }

            // Future UI commands or acknowledgements
            // will be handled here.
        }
    }

    private static async Task
        SendStateUpdatesAsync(
            StreamWriter writer,
            StationCredential credential,
            Guid correlationId,
            ChannelReader<
                StationRuntimeSnapshot
            > reader,
            CancellationToken cancellationToken
        )
    {
        await foreach (
            StationRuntimeSnapshot snapshot
            in reader.ReadAllAsync(
                cancellationToken
            )
        )
        {
            await SendStateAsync(
                writer,
                credential,
                snapshot,
                correlationId
            );
        }
    }

    private static async Task SendStateAsync(
        StreamWriter writer,
        StationCredential credential,
        StationRuntimeSnapshot snapshot,
        Guid correlationId
    )
    {
        StationStateMessage state =
            new(
                IpcProtocol.Version,
                IpcProtocol.StateType,
                Guid.NewGuid(),
                correlationId,
                DateTimeOffset.UtcNow,
                credential.StationId,
                credential.StationCode,
                snapshot.BackendConnected
            );

        string serializedState =
            JsonSerializer.Serialize(
                state,
                IpcProtocol.JsonOptions
            );

        await writer.WriteLineAsync(
            serializedState
        );
    }
    private static NamedPipeServerStream
        CreatePipe()
    {
        if (!OperatingSystem.IsWindows())
        {
            throw new
                PlatformNotSupportedException(
                    "Station IPC requires Windows."
                );
        }

        PipeSecurity security =
            new();

        security.SetAccessRuleProtection(
            isProtected: true,
            preserveInheritance: false
        );

        SecurityIdentifier networkSid =
            new(
                WellKnownSidType.NetworkSid,
                null
            );

        security.AddAccessRule(
            new PipeAccessRule(
                networkSid,
                PipeAccessRights.FullControl,
                AccessControlType.Deny
            )
        );

        SecurityIdentifier
            authenticatedUsersSid =
                new(
                    WellKnownSidType
                        .AuthenticatedUserSid,
                    null
                );

        security.AddAccessRule(
            new PipeAccessRule(
                authenticatedUsersSid,
                PipeAccessRights.ReadWrite,
                AccessControlType.Allow
            )
        );

        SecurityIdentifier systemSid =
            new(
                WellKnownSidType.LocalSystemSid,
                null
            );

        security.AddAccessRule(
            new PipeAccessRule(
                systemSid,
                PipeAccessRights.FullControl,
                AccessControlType.Allow
            )
        );

        SecurityIdentifier administratorsSid =
            new(
                WellKnownSidType
                    .BuiltinAdministratorsSid,
                null
            );

        security.AddAccessRule(
            new PipeAccessRule(
                administratorsSid,
                PipeAccessRights.FullControl,
                AccessControlType.Allow
            )
        );

        return NamedPipeServerStreamAcl.Create(
            IpcProtocol.PipeName,
            PipeDirection.InOut,
            maxNumberOfServerInstances: 1,
            PipeTransmissionMode.Byte,
            PipeOptions.Asynchronous,
            inBufferSize: 4096,
            outBufferSize: 4096,
            security,
            HandleInheritability.None,
            additionalAccessRights:
                (PipeAccessRights)0
        );
    }

    private static async Task
        SendErrorAsync(
            StreamWriter writer,
            Guid? correlationId,
            string code,
            string message
        )
    {
        IpcErrorMessage error =
            new(
                IpcProtocol.Version,
                IpcProtocol.ErrorType,
                Guid.NewGuid(),
                correlationId,
                DateTimeOffset.UtcNow,
                code,
                message
            );

        string serializedError =
            JsonSerializer.Serialize(
                error,
                IpcProtocol.JsonOptions
            );

        await writer.WriteLineAsync(
            serializedError
        );
    }
}