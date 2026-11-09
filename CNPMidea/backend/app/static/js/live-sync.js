(() => {
  window.startLiveSync = (refresh, interval = 4000) => {
    let busy = false;
    let socket;
    let reconnectTimer;
    const heartbeat = setInterval(() => { if (socket?.readyState === WebSocket.OPEN) socket.send("ping"); }, 20000);
    const tick = async () => {
      if (busy || document.hidden) return;
      busy = true;
      try { await refresh(); } catch (_) { /* Keep the view usable during brief network interruptions. */ }
      finally { busy = false; }
    };
    const timer = setInterval(tick, Math.max(interval, 25000));
    const connect = () => {
      const protocol = location.protocol === "https:" ? "wss:" : "ws:";
      socket = new WebSocket(`${protocol}//${location.hostname}:8000/ws/updates`);
      socket.onmessage = event => {
        try { if (JSON.parse(event.data).type === "data_changed") tick(); } catch (_) {}
      };
      socket.onclose = () => { reconnectTimer = setTimeout(connect, 1800); };
      socket.onerror = () => socket.close();
    };
    connect();
    window.addEventListener("online", tick);
    return () => { clearInterval(timer); clearInterval(heartbeat); clearTimeout(reconnectTimer); socket?.close(); window.removeEventListener("online", tick); };
  };
})();
