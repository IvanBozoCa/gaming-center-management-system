using System.IO;
using System.IO.Pipes;
using System.Text;
using System.Text.Json;

using StationAgent.Contracts.Ipc;

namespace StationAgent.UI.Ipc;

public sealed class StationIpcClient :
    IAsyncDisposable
{
    private NamedPipeClientStream? _pipe;
    private StreamReader? _reader;
    private StreamWriter? _writer;

    private Guid _stationId;

    public bool IsConnected =>
        _pipe?.IsConnected == true;

    public async Task<ServiceWelcomeMessage>
        ConnectAsync(
            CancellationToken cancellationToken
        )
    {
        if (IsConnected)
        {
            throw new InvalidOperationException(
                "IPC client is already connected."
            );
        }

        _pipe =
            new NamedPipeClientStream(
                ".",
                IpcProtocol.PipeName,
                PipeDirection.InOut,
                PipeOptions.Asynchronous
            );

        using CancellationTokenSource
            connectionCancellation =
                CancellationTokenSource
                    .CreateLinkedTokenSource(
                        cancellationToken
                    );

        connectionCancellation.CancelAfter(
            TimeSpan.FromSeconds(2)
        );

        await _pipe.ConnectAsync(
            connectionCancellation.Token
        );

        _reader =
            new StreamReader(
                _pipe,
                new UTF8Encoding(false),
                detectEncodingFromByteOrderMarks:
                    false,
                bufferSize: 4096,
                leaveOpen: true
            );

        _writer =
            new StreamWriter(
                _pipe,
                new UTF8Encoding(false),
                bufferSize: 4096,
                leaveOpen: true
            )
            {
                AutoFlush = true,
            };

        Guid helloEventId =
            Guid.NewGuid();

        UiHelloMessage hello =
            new(
                IpcProtocol.Version,
                IpcProtocol.HelloType,
                helloEventId,
                null,
                DateTimeOffset.UtcNow,
                Guid.NewGuid(),
                Environment.ProcessId
            );

        string serializedHello =
            JsonSerializer.Serialize(
                hello,
                IpcProtocol.JsonOptions
            );

        await _writer.WriteLineAsync(
            serializedHello
        );

        string? rawResponse =
            await _reader.ReadLineAsync(
                cancellationToken
            );

        if (rawResponse is null)
        {
            throw new IOException(
                "IPC server disconnected "
                + "during handshake."
            );
        }

        using JsonDocument document =
            JsonDocument.Parse(
                rawResponse
            );

        if (
            !document.RootElement
                .TryGetProperty(
                    "type",
                    out JsonElement typeElement
                )
        )
        {
            throw new InvalidDataException(
                "IPC response has no "
                + "message type."
            );
        }

        string? type =
            typeElement.GetString();

        if (type == IpcProtocol.ErrorType)
        {
            IpcErrorMessage? error =
                JsonSerializer.Deserialize<
                    IpcErrorMessage
                >(
                    rawResponse,
                    IpcProtocol.JsonOptions
                );

            throw new InvalidDataException(
                error?.Message
                ?? "IPC server returned an error."
            );
        }

        if (type != IpcProtocol.WelcomeType)
        {
            throw new InvalidDataException(
                $"Unexpected IPC message: {type}"
            );
        }

        ServiceWelcomeMessage? welcome =
            JsonSerializer.Deserialize<
                ServiceWelcomeMessage
            >(
                rawResponse,
                IpcProtocol.JsonOptions
            );

        if (
            welcome is null
            || welcome.Version
                != IpcProtocol.Version
            || welcome.EventId
                == Guid.Empty
            || welcome.CorrelationId
                != helloEventId
            || welcome.StationId
                == Guid.Empty
            || string.IsNullOrWhiteSpace(
                welcome.StationCode
            )
        )
        {
            throw new InvalidDataException(
                "Invalid WELCOME message."
            );
        }

        _stationId =
            welcome.StationId;

        return welcome;
    }

    public async Task WaitForDisconnectAsync(
        Func<StationStateMessage, Task> onState,
        CancellationToken cancellationToken
    )
    {
        if (
            _pipe is null
            || _reader is null
            || !_pipe.IsConnected
        )
        {
            return;
        }

        while (
            _pipe.IsConnected
            && !cancellationToken
                .IsCancellationRequested
        )
        {
            string? rawMessage =
                await _reader.ReadLineAsync(
                    cancellationToken
                );

            if (rawMessage is null)
            {
                return;
            }

            using JsonDocument document =
                JsonDocument.Parse(
                    rawMessage
                );

            if (
                !document.RootElement
                    .TryGetProperty(
                        "type",
                        out JsonElement
                            typeElement
                    )
            )
            {
                continue;
            }

            string? type =
                typeElement.GetString();

            if (
                type
                    != IpcProtocol.StateType
            )
            {
                continue;
            }

            StationStateMessage? state =
                JsonSerializer.Deserialize<
                    StationStateMessage
                >(
                    rawMessage,
                    IpcProtocol.JsonOptions
                );

            if (
                state is null
                || state.Version
                    != IpcProtocol.Version
                || state.EventId
                    == Guid.Empty
                || state.StationId
                    != _stationId
                || string.IsNullOrWhiteSpace(
                    state.StationCode
                )
            )
            {
                throw new InvalidDataException(
                    "Invalid STATE message."
                );
            }

            await onState(
                state
            );
        }
    }

    public async ValueTask DisposeAsync()
    {
        if (_writer is not null)
        {
            await _writer.DisposeAsync();
        }

        _reader?.Dispose();

        if (_pipe is not null)
        {
            await _pipe.DisposeAsync();
        }
    }
}