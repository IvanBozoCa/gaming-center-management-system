using System.Text.Json;

namespace StationAgent.Contracts.Ipc;

public static class IpcProtocol
{
    public const int Version = 1;

    public const string PipeName =
        "GamingCenter.StationAgent";

    public const string HelloType =
        "HELLO";

    public const string WelcomeType =
        "WELCOME";

    public const string StateType =
        "STATE";

    public const string ErrorType =
        "ERROR";

    public static JsonSerializerOptions JsonOptions
        { get; } = new()
        {
            PropertyNamingPolicy =
                JsonNamingPolicy.SnakeCaseLower,
        };
}

public sealed record UiHelloMessage(
    int Version,
    string Type,
    Guid EventId,
    Guid? CorrelationId,
    DateTimeOffset SentAt,
    Guid UiInstanceId,
    int ProcessId
);

public sealed record ServiceWelcomeMessage(
    int Version,
    string Type,
    Guid EventId,
    Guid? CorrelationId,
    DateTimeOffset SentAt,
    Guid StationId,
    string StationCode
);

public sealed record StationStateMessage(
    int Version,
    string Type,
    Guid EventId,
    Guid? CorrelationId,
    DateTimeOffset SentAt,
    Guid StationId,
    string StationCode,
    bool BackendConnected
);

public sealed record IpcErrorMessage(
    int Version,
    string Type,
    Guid EventId,
    Guid? CorrelationId,
    DateTimeOffset SentAt,
    string Code,
    string Message
);