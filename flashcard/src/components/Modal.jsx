export default function Modal({ open, title, onClose, children, wide }) {
  if (!open) return null;
  return (
    <div className="modal-backdrop" onClick={e => e.target === e.currentTarget && onClose()}>
      <div className="modal" style={wide ? { maxWidth: 640 } : {}}>
        <div className="modal-title">{title}</div>
        {children}
      </div>
    </div>
  );
}
