// ArMqttClient.cs
// Minimal MQTT client for an AR app (Unity C# style) using MQTTnet.
// Place in: Assets/Scripts/Networking/ArMqttClient.cs
//
// NOTE: In Unity you must add MQTTnet via NuGet (or Unity package import).
// This script shows the logic clearly even if you later swap the MQTT library.

using System;
using System.Text;
using System.Threading.Tasks;
using UnityEngine;

// MQTTnet namespaces (requires MQTTnet library)
using MQTTnet;
using MQTTnet.Client;
using MQTTnet.Client.Options;

[Serializable]
public class WorkstationRequest
{
    public bool all;
    public string workstation_id;
}

public class ArMqttClient : MonoBehaviour
{
    [Header("Broker Settings")]
    [Tooltip("Example: 10.0.0.21 (broker in factory network)")]
    public string brokerHost = "localhost";
    public int brokerPort = 1883;

    [Header("Topics")]
    public string requestTopic = "ar/workstation/request";
    public string responseTopic = "ar/workstation/response";

    [Header("Demo Input")]
    public string workstationId = "WS_AR_001";

    private IMqttClient _client;

    private async void Start()
    {
        await ConnectAndSubscribe();
    }

    private async Task ConnectAndSubscribe()
    {
        var factory = new MqttFactory();
        _client = factory.CreateMqttClient();

        _client.ApplicationMessageReceivedAsync += e =>
        {
            string payload = Encoding.UTF8.GetString(e.ApplicationMessage.PayloadSegment);
            Debug.Log($"MQTT RX topic={e.ApplicationMessage.Topic} payload={payload}");

            // In a real AR app you would parse JSON here and apply config.
            // For now we just log the response.
            return Task.CompletedTask;
        };

        var options = new MqttClientOptionsBuilder()
            .WithTcpServer(brokerHost, brokerPort)
            .Build();

        try
        {
            await _client.ConnectAsync(options);
            Debug.Log("MQTT connected");

            await _client.SubscribeAsync(responseTopic);
            Debug.Log($"MQTT subscribed: {responseTopic}");
        }
        catch (Exception ex)
        {
            Debug.LogError($"MQTT connect/subscribe failed: {ex.Message}");
        }
    }

    // Call this when workstation is detected
    public async void RequestOne(string wsId)
    {
        if (_client == null || !_client.IsConnected)
        {
            Debug.LogWarning("MQTT not connected yet.");
            return;
        }

        var reqObj = new WorkstationRequest { all = false, workstation_id = wsId };
        string json = JsonUtility.ToJson(reqObj);

        var msg = new MqttApplicationMessageBuilder()
            .WithTopic(requestTopic)
            .WithPayload(json)
            .WithAtLeastOnceQoS()
            .Build();

        await _client.PublishAsync(msg);
        Debug.Log($"MQTT TX request one: {json}");
    }

    public async void RequestAll()
    {
        if (_client == null || !_client.IsConnected)
        {
            Debug.LogWarning("MQTT not connected yet.");
            return;
        }

        var reqObj = new WorkstationRequest { all = true, workstation_id = "" };
        string json = JsonUtility.ToJson(reqObj);

        var msg = new MqttApplicationMessageBuilder()
            .WithTopic(requestTopic)
            .WithPayload(json)
            .WithAtLeastOnceQoS()
            .Build();

        await _client.PublishAsync(msg);
        Debug.Log($"MQTT TX request all: {json}");
    }

    [ContextMenu("Demo: MQTT Request One")]
    public void DemoRequestOne()
    {
        RequestOne(workstationId);
    }

    [ContextMenu("Demo: MQTT Request All")]
    public void DemoRequestAll()
    {
        RequestAll();
    }

    private async void OnDestroy()
    {
        try
        {
            if (_client != null && _client.IsConnected)
                await _client.DisconnectAsync();
        }
        catch { /* ignore */ }
    }
}