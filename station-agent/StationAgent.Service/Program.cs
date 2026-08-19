using StationAgent.Service;
using StationAgent.Service.Configuration;

HostApplicationBuilder builder =
    Host.CreateApplicationBuilder(args);

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
                backendUri.Scheme == Uri.UriSchemeHttp
                || backendUri.Scheme == Uri.UriSchemeHttps
            ),
        "StationAgent:BackendBaseUrl must be an absolute HTTP or HTTPS URL."
    )
    .Validate(
        options =>
            options.IdleLogIntervalSeconds >= 10,
        "StationAgent:IdleLogIntervalSeconds must be at least 10 seconds."
    )
    .ValidateOnStart();

builder.Services.AddHostedService<Worker>();

IHost host = builder.Build();

host.Run();
