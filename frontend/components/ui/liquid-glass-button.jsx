import { forwardRef } from "react";

export const LiquidButton = forwardRef(function LiquidButton(
  { children, className = "", type = "button", ...props },
  ref,
) {
  return (
    <button
      ref={ref}
      type={type}
      className={`liquid-button ${className}`.trim()}
      {...props}
    >
      {children}
    </button>
  );
});
