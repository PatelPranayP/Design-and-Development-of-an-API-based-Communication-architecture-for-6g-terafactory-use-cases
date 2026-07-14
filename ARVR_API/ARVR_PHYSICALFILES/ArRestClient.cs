// ArRestClient.cs
// Minimal REST client for an AR app (Unity C# style).
// Place in: Assets/Scripts/Networking/ArRestClient.cs

using System;
using System.Collections;
using UnityEngine;
using UnityEngine.Networking;

[Serializable]
public class WorkstationConfig
{
    public string workstation_id;
    public string name;
    public string location;
    public string status;
    public string ui_mode;
    public string[] supported_devices;
    public string[] required_inputs;
}

public class ArRestClient : MonoBehaviour
{
    [Header("Backend Settings")]
    [Tooltip("Example: http://10.0.0.20:8001 (factory/edge server)")]
    public string backendBaseUrl = "http://localhost:8001";

    [Header("Demo Input")]
    public string workstationId = "WS_AR_001";

    // Call this when the AR app detects a workstation (QR/NFC/manual selection)
    public void RequestWorkstationConfig(string wsId)
    {
        StartCoroutine(GetWorkstationConfigCoroutine(wsId));
    }

    // Demo button: request the workstationId above
    [ContextMenu("Demo: Request Config")]
    public void DemoRequest()
    {
        RequestWorkstationConfig(workstationId);
    }

    private IEnumerator GetWorkstationConfigCoroutine(string wsId)
    {
        string url = $"{backendBaseUrl}/api/ar/workstations/{wsId}";
        using (UnityWebRequest req = UnityWebRequest.Get(url))
        {
            req.timeout = 10;
            yield return req.SendWebRequest();

#if UNITY_2020_2_OR_NEWER
            bool isError = req.result != UnityWebRequest.Result.Success;
#else
            bool isError = req.isNetworkError || req.isHttpError;
#endif

            if (isError)
            {
                Debug.LogError($"REST error: {req.responseCode} {req.error} URL={url}");
                yield break;
            }

            string json = req.downloadHandler.text;
            Debug.Log($"REST raw JSON: {json}");

            // Parse JSON into object
            WorkstationConfig cfg = JsonUtility.FromJson<WorkstationConfig>(json);
            if (cfg == null || string.IsNullOrEmpty(cfg.workstation_id))
            {
                Debug.LogError("REST parse failed or invalid JSON shape. Ensure backend returns fields matching WorkstationConfig.");
                yield break;
            }

            ApplyConfig(cfg);
        }
    }

    // Here you would wire into your AR UI/workflow logic
    private void ApplyConfig(WorkstationConfig cfg)
    {
        Debug.Log($"APPLY CONFIG: id={cfg.workstation_id}, mode={cfg.ui_mode}, status={cfg.status}");
        // Example: if (cfg.ui_mode == "assembly_guidance") { ... }
        // Example: show UI, request required_inputs, etc.
    }
}