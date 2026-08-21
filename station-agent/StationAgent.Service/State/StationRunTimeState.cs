namespace StationAgent.Service.State;

public sealed record StationRuntimeSnapshot(
    bool BackendConnected
);

public sealed class StationRuntimeState
{
    private int _backendConnected;

    public event Action<StationRuntimeSnapshot>?
        Changed;

    public StationRuntimeSnapshot GetSnapshot()
    {
        return new StationRuntimeSnapshot(
            Volatile.Read(
                ref _backendConnected
            ) == 1
        );
    }

    public void SetBackendConnected(
        bool connected
    )
    {
        int newValue =
            connected ? 1 : 0;

        int previousValue =
            Interlocked.Exchange(
                ref _backendConnected,
                newValue
            );

        if (previousValue == newValue)
        {
            return;
        }

        Changed?.Invoke(
            new StationRuntimeSnapshot(
                connected
            )
        );
    }
}