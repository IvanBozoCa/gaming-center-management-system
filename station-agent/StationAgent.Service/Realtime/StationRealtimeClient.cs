using System.Net.WebSockets;
using System.Text;
using System.Text.Json;

using Microsoft.Extensions.Options;

using StationAgent.Service.Configuration;
using StationAgent.Service.Security;
using StationAgent.Service.State;

namespace StationAgent.Service.Realtime;

public sealed class StationRealtimeClient(
    ILogger<StationRealtimeClient> logger,
    IOptions<StationAgentOptions> options,
    StationRuntimeState runtimeState
)
{
    private const int MaxServerMessageBytes =
        64 * 1024;

    private readonly ILogger<
        StationRealtimeClient
    > _logger = logger;

    private readonly StationAgentOptions
        _options = options.Value;

    private readonly StationRuntimeState
        _runtimeState = runtimeState;

    public async Task RunAsync(
        StationCredential credential,
        CancellationToken stoppingToken
    )
    {
        int failureCount = 0;

        while (
            !stoppingToken
                .IsCancellationRequested
        )
        {
            try
            {
                await RunSessionAsync(
                    credential,
                    stoppingToken
                );

                failureCount = 0;
            }
            catch (OperationCanceledException)
                when (
                    stoppingToken
                        .IsCancellationRequested
                )
            {
                break;
            }
            catch (Exception exception)
            {
                _logger.LogWarning(
                    exception,
                    "Realtime connection failed. "
                    + "StationCode={StationCode}",
                    credential.StationCode
                );
            }
            finally
            {
                _runtimeState.SetBackendConnected(
                    false
                );
            }

            if (
                stoppingToken
                    .IsCancellationRequested
            )
            {
                break;
            }

            TimeSpan delay =
                CalculateReconnectDelay(
                    failureCount
                );

            failureCount++;

            _logger.LogInformation(
                "Realtime reconnect scheduled "
                + "in {DelayMilliseconds} ms. "
                + "Attempt={Attempt}",
                delay.TotalMilliseconds,
                failureCount
            );

            try
            {
                await Task.Delay(
                    delay,
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
        }
    }

    private async Task RunSessionAsync(
        StationCredential credential,
        CancellationToken stoppingToken
    )
    {
        using ClientWebSocket websocket =
            new();

        websocket.Options.SetRequestHeader(
            "Authorization",
            $"Bearer {credential.AgentToken}"
        );

        Uri websocketUri =
            BuildWebSocketUri();

        _logger.LogInformation(
            "Connecting realtime channel. "
            + "StationCode={StationCode} "
            + "Endpoint={Endpoint}",
            credential.StationCode,
            websocketUri
        );

        await websocket.ConnectAsync(
            websocketUri,
            stoppingToken
        );

        _logger.LogInformation(
            "WebSocket transport connected. "
            + "StationCode={StationCode}",
            credential.StationCode
        );

        ConnectedMessageData connected =
            await ReceiveConnectedMessageAsync(
                websocket,
                credential,
                stoppingToken
            );
        _runtimeState.SetActiveSession(
            MapActiveSession(
                connected.ActiveSession
            )
        );

        _logger.LogInformation(
            "Station realtime session established. "
            + "StationCode={StationCode} "
            + "HeartbeatInterval={HeartbeatInterval}s",
            credential.StationCode,
            connected.HeartbeatIntervalSeconds
        );
        _runtimeState.SetBackendConnected(
            true
        );

        using CancellationTokenSource
            sessionCancellation =
                CancellationTokenSource
                    .CreateLinkedTokenSource(
                        stoppingToken
                    );

        Task receiveTask =
            ReceiveLoopAsync(
                websocket,
                sessionCancellation.Token
            );

        Task heartbeatTask =
            HeartbeatLoopAsync(
                websocket,
                TimeSpan.FromSeconds(
                    connected
                        .HeartbeatIntervalSeconds
                ),
                sessionCancellation.Token
            );

        Task completedTask =
            await Task.WhenAny(
                receiveTask,
                heartbeatTask
            );

        sessionCancellation.Cancel();

        try
        {
            await Task.WhenAll(
                receiveTask,
                heartbeatTask
            );
        }
        catch
        {
            // The task that ended the session
            // is inspected immediately below.
        }

        if (completedTask.IsFaulted)
        {
            await completedTask;
        }

        if (
            stoppingToken
                .IsCancellationRequested
        )
        {
            return;
        }

        await CloseSocketSafelyAsync(
            websocket
        );
    }


    private async Task<
        ConnectedMessageData
    > ReceiveConnectedMessageAsync(
        ClientWebSocket websocket,
        StationCredential credential,
        CancellationToken cancellationToken
    )
    {
        string? rawMessage =
            await ReceiveTextMessageAsync(
                websocket,
                cancellationToken
            );

        if (rawMessage is null)
        {
            throw new WebSocketException(
                "Server closed the WebSocket "
                + "before CONNECTED was received."
            );
        }

        ServerAgentMessage message =
            DeserializeServerMessage(
                rawMessage
            );

        if (
            message.Version
                != AgentProtocol.Version
            || message.Type
                != AgentProtocol
                    .ConnectedType
        )
        {
            throw new InvalidDataException(
                "Expected CONNECTED message "
                + "from server."
            );
        }

        ConnectedMessageData? data =
            message.Data.Deserialize<
                ConnectedMessageData
            >(
                AgentProtocol.JsonOptions
            );

        if (data is null)
        {
            throw new InvalidDataException(
                "CONNECTED message data "
                + "is missing."
            );
        }

        if (
            data.StationId
                != credential.StationId
        )
        {
            throw new InvalidDataException(
                "CONNECTED station id "
                + "does not match enrolled station."
            );
        }

        if (
            data.HeartbeatIntervalSeconds
                < 1
        )
        {
            throw new InvalidDataException(
                "Invalid heartbeat interval "
                + "received from server."
            );
        }

        return data;
    }


    private async Task HeartbeatLoopAsync(
        ClientWebSocket websocket,
        TimeSpan interval,
        CancellationToken cancellationToken
    )
    {
        using PeriodicTimer timer =
            new(interval);

        while (
            await timer.WaitForNextTickAsync(
                cancellationToken
            )
        )
        {
            Guid eventId =
                Guid.NewGuid();

            AgentHeartbeatMessage heartbeat =
                new(
                    Version:
                        AgentProtocol.Version,
                    Type:
                        AgentProtocol
                            .HeartbeatType,
                    EventId:
                        eventId,
                    CorrelationId:
                        null,
                    SentAt:
                        DateTimeOffset.UtcNow
                );

            byte[] payload =
                JsonSerializer
                    .SerializeToUtf8Bytes(
                        heartbeat,
                        AgentProtocol
                            .JsonOptions
                    );

            await websocket.SendAsync(
                new ArraySegment<byte>(
                    payload
                ),
                WebSocketMessageType.Text,
                endOfMessage: true,
                cancellationToken
            );

            _logger.LogDebug(
                "Heartbeat sent. "
                + "EventId={EventId}",
                eventId
            );
        }
    }


    private async Task ReceiveLoopAsync(
        ClientWebSocket websocket,
        CancellationToken cancellationToken
    )
    {
        while (
            !cancellationToken
                .IsCancellationRequested
        )
        {
            string? rawMessage =
                await ReceiveTextMessageAsync(
                    websocket,
                    cancellationToken
                );

            if (rawMessage is null)
            {
                _logger.LogWarning(
                    "Realtime channel closed "
                    + "by server."
                );

                return;
            }

            ServerAgentMessage message =
                DeserializeServerMessage(
                    rawMessage
                );

            if (
                message.Version
                    != AgentProtocol.Version
            )
            {
                throw new InvalidDataException(
                    "Unsupported server "
                    + "protocol version."
                );
            }

            switch (message.Type)
            {
                case AgentProtocol
                    .HeartbeatAckType:

                    _logger.LogDebug(
                        "Heartbeat acknowledged. "
                        + "CorrelationId={CorrelationId}",
                        message.CorrelationId
                    );

                    break;

                case AgentProtocol
                    .SessionStartType:

                case AgentProtocol
                    .SessionExtendType:
                    {
                        AgentSessionData? session =
                            message.Data.Deserialize<
                                AgentSessionData
                            >(
                                AgentProtocol.JsonOptions
                            );

                        StationSessionSnapshot snapshot =
                            MapActiveSession(
                                session
                            )
                            ?? throw new InvalidDataException(
                                "Session event does not "
                                + "contain an active session."
                            );

                        _runtimeState.SetActiveSession(
                            snapshot
                        );

                        _logger.LogInformation(
                            "Station session synchronized. "
                            + "Type={MessageType} "
                            + "SessionId={SessionId} "
                            + "SessionType={SessionType} "
                            + "RemainingSeconds={RemainingSeconds}",
                            message.Type,
                            snapshot.SessionId,
                            snapshot.SessionType,
                            snapshot.RemainingSeconds
                        );

                        break;
                    }


                case AgentProtocol
                    .SessionFinishType:
                    {
                        SessionFinishData? finished =
                            message.Data.Deserialize<
                                SessionFinishData
                            >(
                                AgentProtocol.JsonOptions
                            );

                        if (
                            finished is null
                            || finished.SessionId
                                == Guid.Empty
                            || finished.SessionType
                                is not (
                                    "REGISTERED"
                                    or "GUEST"
                                )
                        )
                        {
                            throw new InvalidDataException(
                                "Invalid SESSION_FINISH "
                                + "message received."
                            );
                        }

                        bool applied =
                            _runtimeState.FinishSession(
                                finished.SessionId
                            );

                        if (applied)
                        {
                            _logger.LogInformation(
                                "Station session finished. "
                                + "SessionId={SessionId} "
                                + "SessionType={SessionType}",
                                finished.SessionId,
                                finished.SessionType
                            );
                        }
                        else
                        {
                            _logger.LogDebug(
                                "SESSION_FINISH ignored because "
                                + "the session is no longer active. "
                                + "SessionId={SessionId}",
                                finished.SessionId
                            );
                        }

                        break;
                    }


                case AgentProtocol.ErrorType:
                    ServerErrorData? error =
                        message.Data.Deserialize<
                            ServerErrorData
                        >(
                            AgentProtocol
                                .JsonOptions
                        );

                    _logger.LogWarning(
                        "Server reported realtime "
                        + "protocol error. "
                        + "Code={Code}",
                        error?.Code
                    );

                    break;


                default:
                    throw new InvalidDataException(
                        $"Unexpected server message "
                        + $"type: {message.Type}"
                    );
            }
        }
    }


    private static ServerAgentMessage
        DeserializeServerMessage(
            string rawMessage
        )
    {
        ServerAgentMessage? message =
            JsonSerializer.Deserialize<
                ServerAgentMessage
            >(
                rawMessage,
                AgentProtocol.JsonOptions
            );

        return message
            ?? throw new InvalidDataException(
                "Server returned an invalid "
                + "realtime message."
            );
    }


    private async Task<string?>
        ReceiveTextMessageAsync(
            ClientWebSocket websocket,
            CancellationToken cancellationToken
        )
    {
        byte[] buffer =
            new byte[4096];

        using MemoryStream messageBuffer =
            new();

        while (true)
        {
            WebSocketReceiveResult result =
                await websocket.ReceiveAsync(
                    new ArraySegment<byte>(
                        buffer
                    ),
                    cancellationToken
                );

            if (
                result.MessageType
                    == WebSocketMessageType.Close
            )
            {
                return null;
            }

            if (
                result.MessageType
                    != WebSocketMessageType.Text
            )
            {
                throw new InvalidDataException(
                    "Server WebSocket messages "
                    + "must be text."
                );
            }

            await messageBuffer.WriteAsync(
                buffer.AsMemory(
                    0,
                    result.Count
                ),
                cancellationToken
            );

            if (
                messageBuffer.Length
                    > MaxServerMessageBytes
            )
            {
                throw new InvalidDataException(
                    "Server WebSocket message "
                    + "exceeded maximum size."
                );
            }

            if (result.EndOfMessage)
            {
                return Encoding.UTF8.GetString(
                    messageBuffer.ToArray()
                );
            }
        }
    }
    private static StationSessionSnapshot?
    MapActiveSession(
        AgentSessionData? session
    )
    {
        if (session is null)
        {
            return null;
        }

        if (
            session.SessionId
                == Guid.Empty
            || session.AuthorizedSeconds <= 0
            || session.ElapsedSeconds < 0
            || session.RemainingSeconds < 0
            || session.SessionType
                is not (
                    "REGISTERED"
                    or "GUEST"
                )
            || session.TimeState
                is not (
                    "RUNNING"
                    or "EXHAUSTED"
                )
        )
        {
            throw new InvalidDataException(
                "Invalid active session "
                + "received from backend."
            );
        }

        return new StationSessionSnapshot(
            session.SessionId,
            session.SessionType,
            session.AuthorizedSeconds,
            session.StartedAt,
            session.ServerNow,
            session.ElapsedSeconds,
            session.RemainingSeconds,
            session.TimeState
        );
    }


    private TimeSpan
        CalculateReconnectDelay(
            int failureCount
        )
    {
        int boundedFailureCount =
            Math.Min(
                failureCount,
                20
            );

        double multiplier =
            Math.Pow(
                2,
                boundedFailureCount
            );

        double delaySeconds =
            Math.Min(
                _options
                    .ReconnectMaxDelaySeconds,
                _options
                    .ReconnectInitialDelaySeconds
                * multiplier
            );

        int jitterMilliseconds =
            _options
                .ReconnectJitterMilliseconds
            == 0
                ? 0
                : Random.Shared.Next(
                    0,
                    _options
                        .ReconnectJitterMilliseconds
                    + 1
                );

        return TimeSpan.FromMilliseconds(
            delaySeconds * 1000
            + jitterMilliseconds
        );
    }


    private Uri BuildWebSocketUri()
    {
        Uri backendUri =
            new(
                _options.BackendBaseUrl,
                UriKind.Absolute
            );

        UriBuilder builder =
            new(backendUri)
            {
                Scheme =
                    backendUri.Scheme
                        == Uri.UriSchemeHttps
                        ? "wss"
                        : "ws",

                Query = string.Empty,

                Fragment = string.Empty,
            };

        if (backendUri.IsDefaultPort)
        {
            builder.Port = -1;
        }

        string basePath =
            backendUri.AbsolutePath
                .TrimEnd('/');

        builder.Path =
            $"{basePath}/agent/ws";

        return builder.Uri;
    }


    private static async Task
        CloseSocketSafelyAsync(
            ClientWebSocket websocket
        )
    {
        if (
            websocket.State
                is not (
                    WebSocketState.Open
                    or WebSocketState
                        .CloseReceived
                )
        )
        {
            return;
        }

        using CancellationTokenSource
            closeTimeout =
                new(
                    TimeSpan.FromSeconds(2)
                );

        try
        {
            await websocket
                .CloseOutputAsync(
                    WebSocketCloseStatus
                        .NormalClosure,
                    "Station Agent "
                    + "reconnecting",
                    closeTimeout.Token
                );
        }
        catch (
            OperationCanceledException
        )
        {
            // Best-effort shutdown only.
        }
        catch (WebSocketException)
        {
            // Connection is already broken.
        }
    }
}