namespace StationAgent.Service.Configuration;

public sealed class StationAgentOptions
{
    public const string SectionName =
        "StationAgent";

    public string BackendBaseUrl
    {
        get;
        init;
    } = "http://127.0.0.1:8000";

    public int IdleLogIntervalSeconds
    {
        get;
        init;
    } = 60;
}