using System.Net;
using System.Net.Http.Headers;
using System.Net.Http.Json;
using System.Text;
using System.Text.Json.Serialization;

using Microsoft.Extensions.Options;

using StationAgent.Service.Configuration;
using StationAgent.Service.Security;

namespace StationAgent.Service.Enrollment;

public sealed class StationEnrollmentCommand(
    IOptions<StationAgentOptions> options,
    StationCredentialStore credentialStore
)
{
    private readonly StationAgentOptions _options =
        options.Value;

    private readonly StationCredentialStore
        _credentialStore = credentialStore;

    public async Task<int> RunAsync(
        CancellationToken cancellationToken
    )
    {
        Console.WriteLine(
            "Gaming Center Station Agent enrollment"
        );

        Console.Write(
            "Agent token (input is hidden): "
        );

        string token =
            ReadHiddenLine().Trim();

        if (string.IsNullOrWhiteSpace(token))
        {
            Console.Error.WriteLine(
                "Agent token is required."
            );

            return 1;
        }

        try
        {
            using HttpClient client =
                new()
                {
                    BaseAddress = new Uri(
                        _options.BackendBaseUrl
                            .TrimEnd('/')
                        + "/"
                    ),
                    Timeout =
                        TimeSpan.FromSeconds(15),
                };

            client.DefaultRequestHeaders
                .Authorization =
                    new AuthenticationHeaderValue(
                        "Bearer",
                        token
                    );

            using HttpResponseMessage response =
                await client.GetAsync(
                    "agent/station",
                    cancellationToken
                );

            if (
                response.StatusCode
                == HttpStatusCode.Unauthorized
            )
            {
                Console.Error.WriteLine(
                    "The agent token is invalid or revoked."
                );

                return 1;
            }

            if (!response.IsSuccessStatusCode)
            {
                Console.Error.WriteLine(
                    "Backend rejected enrollment. "
                    + $"HTTP {(int)response.StatusCode}."
                );

                return 1;
            }

            EnrollmentStationResponse? station =
                await response.Content
                    .ReadFromJsonAsync<
                        EnrollmentStationResponse
                    >(cancellationToken);

            if (
                station is null
                || station.Id == Guid.Empty
                || string.IsNullOrWhiteSpace(
                    station.Code
                )
            )
            {
                Console.Error.WriteLine(
                    "Backend returned an invalid station identity."
                );

                return 1;
            }

            _credentialStore.Save(
                new StationCredential(
                    station.Id,
                    station.Code,
                    token
                )
            );

            Console.WriteLine();
            Console.WriteLine(
                $"Station enrolled: {station.Code}"
            );
            Console.WriteLine(
                $"Station ID: {station.Id}"
            );
            Console.WriteLine(
                "Credential stored securely at:"
            );
            Console.WriteLine(
                _credentialStore.CredentialPath
            );

            return 0;
        }
        catch (OperationCanceledException)
        {
            Console.Error.WriteLine(
                "Enrollment request timed out or was cancelled."
            );

            return 1;
        }
        catch (Exception exception)
        {
            Console.Error.WriteLine(
                $"Enrollment failed: {exception.Message}"
            );

            return 1;
        }
    }

    private static string ReadHiddenLine()
    {
        StringBuilder value = new();

        while (true)
        {
            ConsoleKeyInfo key =
                Console.ReadKey(
                    intercept: true
                );

            if (key.Key == ConsoleKey.Enter)
            {
                Console.WriteLine();
                break;
            }

            if (key.Key == ConsoleKey.Backspace)
            {
                if (value.Length > 0)
                {
                    value.Length--;
                }

                continue;
            }

            if (!char.IsControl(key.KeyChar))
            {
                value.Append(key.KeyChar);
            }
        }

        return value.ToString();
    }

    private sealed class EnrollmentStationResponse
    {
        [JsonPropertyName("id")]
        public Guid Id
        {
            get;
            init;
        }

        [JsonPropertyName("code")]
        public string Code
        {
            get;
            init;
        } = string.Empty;
    }
}