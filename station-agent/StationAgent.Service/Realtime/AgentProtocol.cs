using System.Text.Json;

namespace StationAgent.Service.Realtime;

internal static class AgentProtocol
{
    public const int Version = 1;

    public const string ConnectedType =
        "CONNECTED";

    public const string HeartbeatType =
        "HEARTBEAT";

    public const string HeartbeatAckType =
        "HEARTBEAT_ACK";

    public const string ErrorType =
        "ERROR";

    public static JsonSerializerOptions
        JsonOptions { get; } = new()
        {
            PropertyNamingPolicy =
                JsonNamingPolicy.SnakeCaseLower,
        };
}


internal sealed record AgentHeartbeatMessage(
    int Version,
    string Type,
    Guid EventId,
    Guid? CorrelationId,
    DateTimeOffset SentAt
);


internal sealed record ServerAgentMessage(
    int Version,
    string Type,
    Guid EventId,
    Guid? CorrelationId,
    DateTimeOffset SentAt,
    JsonElement Data
);


internal sealed record ConnectedMessageData(
    Guid StationId,
    string StationCode,
    int HeartbeatIntervalSeconds
);


internal sealed record ServerErrorData(
    string? Code
);