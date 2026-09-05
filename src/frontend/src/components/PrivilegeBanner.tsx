interface PrivilegeBannerProps {
  elevated: boolean;
  requesting?: boolean;
  onRequest: () => void;
}

const PrivilegeBanner = ({ elevated, requesting, onRequest }: PrivilegeBannerProps) => {
  if (elevated) return null;

  return (
    <div className="privilege-banner" role="status" data-testid="privilege-banner">
      <span className="privilege-banner-icon">🛡️</span>
      <div className="privilege-banner-body">
        <strong>System changes need administrator rights</strong>
        <span>
          OmniCleaner stays unprivileged and will request elevation (UAC / polkit)
          automatically when an operation needs it.
        </span>
      </div>
      <button
        className="btn btn-secondary btn-sm privilege-banner-action"
        data-testid="request-elevation"
        onClick={onRequest}
        disabled={requesting}
      >
        {requesting ? "Requesting…" : "Request admin rights"}
      </button>
    </div>
  );
};

export default PrivilegeBanner;
