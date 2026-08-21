using System.IO;
using System.Windows;
using StationAgent.Contracts.Ipc;
using StationAgent.UI.Ipc;

namespace StationAgent.UI;

public partial class MainWindow : Window
{
    private readonly CancellationTokenSource
        _lifetimeCancellation =
            new();

    public MainWindow()
    {
        InitializeComponent();

        Loaded += OnLoaded;
        Closed += OnClosed;
    }

    private async void OnLoaded(
        object sender,
        RoutedEventArgs e
    )
    {
        await RunIpcConnectionLoopAsync(
            _lifetimeCancellation.Token
        );
    }

    private async Task
        RunIpcConnectionLoopAsync(
            CancellationToken cancellationToken
        )
    {
        while (
            !cancellationToken
                .IsCancellationRequested
        )
        {
            await using StationIpcClient client =
                new();

            try
            {
                ConnectionStatusText.Text =
                    "IPC: conectando...";

                ServiceWelcomeMessage welcome =
                    await client.ConnectAsync(
                        cancellationToken
                    );

                StationCodeText.Text =
                    welcome.StationCode;

                ConnectionStatusText.Text =
                    "IPC: conectado";

                await client.WaitForDisconnectAsync(
                    state =>
                    {
                        BackendStatusText.Text =
                            state.BackendConnected
                                ? "Backend: conectado"
                                : "Backend: desconectado";

                        return Task.CompletedTask;
                    },
                    cancellationToken
                );

                if (
                    cancellationToken
                        .IsCancellationRequested
                )
                {
                    break;
                }

                ConnectionStatusText.Text =
                    "IPC: servicio no disponible";
                BackendStatusText.Text =
                    "Backend: estado desconocido";
            }
            catch (OperationCanceledException)
                when (
                    cancellationToken
                        .IsCancellationRequested
                )
            {
                break;
            }
            catch (
                OperationCanceledException
            )
            {
                StationCodeText.Text =
                    "Estación no disponible";

                ConnectionStatusText.Text =
                    "IPC: servicio no disponible";
            }
            catch (IOException)
            {
                ConnectionStatusText.Text =
                    "IPC: servicio no disponible";
            }
            catch (Exception)
            {
                StationCodeText.Text =
                    "Estación no disponible";

                ConnectionStatusText.Text =
                    "IPC: servicio no disponible";
            }

            if (
                cancellationToken
                    .IsCancellationRequested
            )
            {
                break;
            }

            ConnectionStatusText.Text =
                "IPC: reconectando...";

            try
            {
                await Task.Delay(
                    TimeSpan.FromSeconds(2),
                    cancellationToken
                );
            }
            catch (OperationCanceledException)
            {
                break;
            }
        }
    }

    private void OnClosed(
        object? sender,
        EventArgs e
    )
    {
        _lifetimeCancellation.Cancel();
        _lifetimeCancellation.Dispose();
    }
}