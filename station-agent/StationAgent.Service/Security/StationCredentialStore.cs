using System.Security.AccessControl;
using System.Security.Cryptography;
using System.Security.Principal;
using System.Text;
using System.Text.Json;

namespace StationAgent.Service.Security;

public sealed record StationCredential(
    Guid StationId,
    string StationCode,
    string AgentToken
);

public sealed class StationCredentialStore
{
    private static readonly byte[] Entropy =
        Encoding.UTF8.GetBytes(
            "GamingCenter.StationAgent.Credential.v1"
        );

    private readonly string _directoryPath =
        Path.Combine(
            Environment.GetFolderPath(
                Environment.SpecialFolder.CommonApplicationData
            ),
            "GamingCenter",
            "StationAgent"
        );

    public string CredentialPath =>
        Path.Combine(
            _directoryPath,
            "identity.dat"
        );

    public bool Exists =>
        File.Exists(CredentialPath);

    public void Save(
        StationCredential credential
    )
    {
        EnsureSecureDirectory();

        byte[] clearData =
            JsonSerializer.SerializeToUtf8Bytes(
                credential
            );

        string temporaryPath =
            CredentialPath + ".tmp";

        try
        {
            byte[] protectedData =
                ProtectedData.Protect(
                    clearData,
                    Entropy,
                    DataProtectionScope.LocalMachine
                );

            File.WriteAllBytes(
                temporaryPath,
                protectedData
            );

            File.Move(
                temporaryPath,
                CredentialPath,
                overwrite: true
            );
        }
        finally
        {
            CryptographicOperations.ZeroMemory(
                clearData
            );

            if (File.Exists(temporaryPath))
            {
                File.Delete(temporaryPath);
            }
        }
    }

    public StationCredential? Load()
    {
        if (!Exists)
        {
            return null;
        }

        byte[] protectedData =
            File.ReadAllBytes(
                CredentialPath
            );

        byte[] clearData =
            ProtectedData.Unprotect(
                protectedData,
                Entropy,
                DataProtectionScope.LocalMachine
            );

        try
        {
            StationCredential? credential =
                JsonSerializer.Deserialize<
                    StationCredential
                >(clearData);

            if (
                credential is null
                || credential.StationId == Guid.Empty
                || string.IsNullOrWhiteSpace(
                    credential.StationCode
                )
                || string.IsNullOrWhiteSpace(
                    credential.AgentToken
                )
            )
            {
                throw new InvalidDataException(
                    "Stored station credential is invalid."
                );
            }

            return credential;
        }
        finally
        {
            CryptographicOperations.ZeroMemory(
                clearData
            );
        }
    }

    private void EnsureSecureDirectory()
    {
        if (!OperatingSystem.IsWindows())
        {
            throw new PlatformNotSupportedException(
                "Station credentials require Windows DPAPI."
            );
        }

        DirectoryInfo directory =
            Directory.CreateDirectory(
                _directoryPath
            );

        DirectorySecurity security =
            new();

        security.SetAccessRuleProtection(
            isProtected: true,
            preserveInheritance: false
        );

        InheritanceFlags inheritance =
            InheritanceFlags.ContainerInherit
            | InheritanceFlags.ObjectInherit;

        security.AddAccessRule(
            new FileSystemAccessRule(
                new SecurityIdentifier(
                    WellKnownSidType.LocalSystemSid,
                    null
                ),
                FileSystemRights.FullControl,
                inheritance,
                PropagationFlags.None,
                AccessControlType.Allow
            )
        );

        security.AddAccessRule(
            new FileSystemAccessRule(
                new SecurityIdentifier(
                    WellKnownSidType.BuiltinAdministratorsSid,
                    null
                ),
                FileSystemRights.FullControl,
                inheritance,
                PropagationFlags.None,
                AccessControlType.Allow
            )
        );

        directory.SetAccessControl(
            security
        );
    }
}