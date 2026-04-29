import { useState, useCallback } from 'react';
export function useToast() {
  const [msg, setMsg] = useState('');
  const [visible, setVisible] = useState(false);
  const show = useCallback((message) => {
    setMsg(message); setVisible(true);
    setTimeout(() => setVisible(false), 2500);
  }, []);
  const Toast = () => <div className={`toast ${visible ? 'show' : ''}`}>{msg}</div>;
  return { show, Toast };
}
