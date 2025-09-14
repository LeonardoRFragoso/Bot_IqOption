import { useEffect, useMemo, useState } from 'react';
import { createTradingSocket } from '../services/ws';

export function useTradingRealtime() {
  const [connected, setConnected] = useState(false);
  const socket = useMemo(() => createTradingSocket(), []);

  useEffect(() => {
    const handleOpen = () => {
      setConnected(true);
      try { socket.send({ type: 'get_status' }); } catch {}
    };
    const handleClose = () => setConnected(false);
    const handlePong = () => {
      // Ask for status on every pong to keep UI fresh
      try { socket.send({ type: 'get_status' }); } catch {}
    };

    socket.on('open', handleOpen);
    socket.on('close', handleClose);
    socket.on('pong', handlePong);

    return () => {
      socket.off('open', handleOpen);
      socket.off('close', handleClose);
      socket.off('pong', handlePong);
      socket.disconnect();
    };
  }, [socket]);

  return { socket, connected };
}
