import { useTheme, type ThemePreference } from "../context/ThemeContext";

const OPTIONS: { value: ThemePreference; label: string; icon: string }[] = [
  { value: "light", label: "Light", icon: "☀️" },
  { value: "dark", label: "Dark", icon: "🌙" },
  { value: "system", label: "Auto", icon: "🖥️" },
];

const ThemeToggle = () => {
  const { preference, setPreference } = useTheme();

  return (
    <div
      className="theme-toggle"
      role="group"
      aria-label="Color theme"
      data-testid="theme-toggle"
    >
      {OPTIONS.map((option) => (
        <button
          key={option.value}
          type="button"
          className="theme-option"
          aria-pressed={preference === option.value}
          aria-label={`${option.label} theme`}
          title={`${option.label} theme`}
          data-testid={`theme-${option.value}`}
          onClick={() => setPreference(option.value)}
        >
          <span className="theme-option-icon" aria-hidden="true">
            {option.icon}
          </span>
          <span className="theme-option-text">{option.label}</span>
        </button>
      ))}
    </div>
  );
};

export default ThemeToggle;
