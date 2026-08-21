using System.Diagnostics;

using Microsoft.Extensions.Options;

using StationAgent.Service.Configuration;
using StationAgent.Service.Security;

namespace StationAgent.Service;

public sealed class Worker(
    ILogger<Worker> logger,
    IOptions<StationAgentOptions> options,
    StationCredentialStore credentialStore
) : BackgroundService
{
    private readonly ILogger<Worker> _logger =
        logger;

    private readonly StationAgentOptions _options =
        options.Value;

    private readonly StationCredentialStore
        _credentialStore = credentialStore;

    protected override async Task ExecuteAsync(
        CancellationToken stoppingToken
    )
    {
        try
        {
            EnsureSafeProcessPriority();

            StationCredential? credential =
                _credentialStore.Load();

            if (credential is null)
            {
                _logger.LogCritical(
                    "Station Agent is not enrolled. "
                    + "Run StationAgent.Service.exe --enroll "
                    + "before starting the service."
                );

                return;
            }

            _logger.LogInformation(
                "Station Agent started. "
                + "StationId={StationId} "
                + "StationCode={StationCode} "
                + "Backend={BackendBaseUrl}",
                credential.StationId,
                credential.StationCode,
                _options.BackendBaseUrl
            );

            using PeriodicTimer timer =
                new(
                    TimeSpan.FromSeconds(
                        _options.IdleLogIntervalSeconds
                    )
                );

            while (
                await timer.WaitForNextTickAsync(
                    stoppingToken
                )
            )
            {
                _logger.LogDebug(
                    "Station Agent service is running. "
                    + "StationCode={StationCode}",
                    credential.StationCode
                );
            }
        }
        catch (OperationCanceledException)
            when (
                stoppingToken
                    .IsCancellationRequested
            )
        {
            // Normal shutdown.
        }
        catch (Exception exception)
        {
            _logger.LogCritical(
                exception,
                "Station Agent stopped because of an unhandled error."
            );

            Environment.Exit(1);
        }

        _logger.LogInformation(
            "Station Agent execution stopped."
        );
    }

    public override async Task StopAsync(
        CancellationToken cancellationToken
    )
    {
        _logger.LogInformation(
            "Station Agent is shutting down."
        );

        await base.StopAsync(
            cancellationToken
        );
    }

    private void EnsureSafeProcessPriority()
    {
        if (!OperatingSystem.IsWindows())
        {
            return;
        }

        using Process process =
            Process.GetCurrentProcess();

        ProcessPriorityClass priority =
            process.PriorityClass;

        if (
            priority is
                ProcessPriorityClass.AboveNormal
                or ProcessPriorityClass.High
                or ProcessPriorityClass.RealTime
        )
        {
            try
            {
                process.PriorityClass =
                    ProcessPriorityClass.Normal;
            }
            catch (Exception exception)
            {
                _logger.LogCritical(
                    exception,
                    "Station Agent could not reduce unsafe process priority."
                );

                throw;
            }
        }

        _logger.LogInformation(
            "Station Agent process priority: {Priority}",
            process.PriorityClass
        );
    }
}