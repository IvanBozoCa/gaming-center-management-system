namespace StationAgent.Service.State;

public sealed record StationSessionSnapshot(
    Guid SessionId,
    string SessionType,
    int AuthorizedSeconds,
    DateTimeOffset StartedAt,
    DateTimeOffset ServerNow,
    int ElapsedSeconds,
    int RemainingSeconds,
    string TimeState
);

public sealed record StationRuntimeSnapshot(
    bool BackendConnected,
    StationSessionSnapshot? ActiveSession
);

public sealed class StationRuntimeState
{
    private readonly object _sync =
        new();

    private bool _backendConnected;

    private StationSessionSnapshot?
        _activeSession;

    public event Action<StationRuntimeSnapshot>?
        Changed;

    public StationRuntimeSnapshot
        GetSnapshot()
    {
        lock (_sync)
        {
            return CreateSnapshot();
        }
    }

    public void SetBackendConnected(
        bool connected
    )
    {
        StationRuntimeSnapshot snapshot;

        lock (_sync)
        {
            if (
                _backendConnected
                    == connected
            )
            {
                return;
            }

            _backendConnected =
                connected;

            snapshot =
                CreateSnapshot();
        }

        Changed?.Invoke(
            snapshot
        );
    }

    public void SetActiveSession(
        StationSessionSnapshot?
            activeSession
    )
    {
        StationRuntimeSnapshot snapshot;

        lock (_sync)
        {
            if (
                Equals(
                    _activeSession,
                    activeSession
                )
            )
            {
                return;
            }

            _activeSession =
                activeSession;

            snapshot =
                CreateSnapshot();
        }

        Changed?.Invoke(
            snapshot
        );
    }

    private StationRuntimeSnapshot
        CreateSnapshot()
    {
        return new StationRuntimeSnapshot(
            _backendConnected,
            _activeSession
        );
    }
}