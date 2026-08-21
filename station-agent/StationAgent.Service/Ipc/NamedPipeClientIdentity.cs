using System.ComponentModel;
using System.Runtime.InteropServices;

using Microsoft.Win32.SafeHandles;

namespace StationAgent.Service.Ipc;

internal static class NamedPipeClientIdentity
{
    public static uint GetClientProcessId(
        SafePipeHandle pipeHandle
    )
    {
        if (
            !GetNamedPipeClientProcessId(
                pipeHandle,
                out uint processId
            )
        )
        {
            throw new Win32Exception(
                Marshal.GetLastWin32Error(),
                "Could not identify Named Pipe client."
            );
        }

        return processId;
    }

    [DllImport(
        "kernel32.dll",
        SetLastError = true
    )]
    [return: MarshalAs(UnmanagedType.Bool)]
    private static extern bool
        GetNamedPipeClientProcessId(
            SafePipeHandle pipe,
            out uint clientProcessId
        );
}