using StationAgent.Service;
using StationAgent.Service.Configuration;
using StationAgent.Service.Enrollment;
using StationAgent.Service.Security;
using StationAgent.Service.Realtime;
using StationAgent.Service.Ipc;
using StationAgent.Service.State;

bool enrollmentRequested =
    args.Any(
        argument =>
            string.Equals(
                argument,
                "--enroll",
                StringComparison.OrdinalIgnoreCase
            )
    );

string[] hostArguments =
    args.Where(
        argument =>
            !string.Equals(
                argument,
                "--enroll",
                StringComparison.OrdinalIgnoreCase
            )
    ).ToArray();

HostApplicationBuilder builder =
    Host.CreateApplicationBuilder(
        hostArguments
    );

builder.Services.AddWindowsService(
    options =>
    {
        options.ServiceName =
            "GamingCenterStationAgent";
    }
);

builder.Services
    .AddOptions<StationAgentOptions>()
    .Bind(
        builder.Configuration.GetSection(
            StationAgentOptions.SectionName
        )
    )
    .Validate(
        options =>
            Uri.TryCreate(
                options.BackendBaseUrl,
                UriKind.Absolute,
                out Uri? backendUri
            )
            && (
                backendUri.Scheme
                    == Uri.UriSchemeHttp
                || backendUri.Scheme
                    == Uri.UriSchemeHttps
            ),
        "StationAgent:BackendBaseUrl must be an absolute HTTP or HTTPS URL."
    )
    .Validate(
        options =>
            options.IdleLogIntervalSeconds >= 10,
        "StationAgent:IdleLogIntervalSeconds must be at least 10 seconds."
    )
    .Validate(
        options =>
            options.ReconnectInitialDelaySeconds
                >= 1,
        "StationAgent:ReconnectInitialDelaySeconds must be at least 1 second."
    )
    .Validate(
        options =>
            options.ReconnectMaxDelaySeconds
                >= options
                    .ReconnectInitialDelaySeconds,
        "StationAgent:ReconnectMaxDelaySeconds must be greater than or equal to the initial delay."
    )
    .Validate(
        options =>
            options.ReconnectJitterMilliseconds
                is >= 0 and <= 5000,
        "StationAgent:ReconnectJitterMilliseconds must be between 0 and 5000."
    )
    .ValidateOnStart();

builder.Services.AddSingleton<
    StationCredentialStore
>();

builder.Services.AddSingleton<
    StationEnrollmentCommand
>();

builder.Services.AddSingleton<
    StationRealtimeClient
>();

builder.Services.AddHostedService<
    StationIpcServer
>();

builder.Services.AddSingleton<
    StationRuntimeState
>();

builder.Services.AddHostedService<Worker>();

using IHost host = builder.Build();

if (enrollmentRequested)
{
    StationEnrollmentCommand command =
        host.Services.GetRequiredService<
            StationEnrollmentCommand
        >();

    return await command.RunAsync(
        CancellationToken.None
    );
}

await host.RunAsync();

return 0;