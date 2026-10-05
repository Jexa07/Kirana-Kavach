import React, { useEffect } from "react";
import { Check, Crown, Sparkles, X } from "lucide-react";

interface PlansModalProps {
  isOpen: boolean;
  onClose: () => void;
  currentPlan: string;
  onSelectPlan: (planId: string) => void;
}

export const PlansModal: React.FC<PlansModalProps> = ({
  isOpen,
  onClose,
  currentPlan,
  onSelectPlan,
}) => {
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === "Escape") onClose();
    };
    if (isOpen) {
      document.body.style.overflow = "hidden";
      window.addEventListener("keydown", handleKeyDown);
    }
    return () => {
      document.body.style.overflow = "unset";
      window.removeEventListener("keydown", handleKeyDown);
    };
  }, [isOpen, onClose]);

  if (!isOpen) return null;

  const plans = [
    {
      id: "free",
      name: "Free",
      price: "₹0",
      period: "/month",
      description: "Basic features for small shop owners",
      features: [
        "Basic business alerts",
        "Limited AI insights",
        "Standard merchant dashboard",
      ],
      recommended: false,
    },
    {
      id: "growth",
      name: "Growth",
      price: "₹249",
      period: "/month",
      description: "Ideal for growing Kirana stores",
      features: [
        "Voice AI copilot",
        "Customer-drop detection",
        "AI recommendations",
        "Customer reactivation workflows",
        "Payment-link actions",
      ],
      recommended: true,
    },
    {
      id: "pro",
      name: "Pro",
      price: "₹499",
      period: "/month",
      description: "Advanced automation for high volume stores",
      features: [
        "Everything in Growth",
        "Advanced automation",
        "More reactivation campaigns",
        "Deeper business insights",
        "Priority merchant support",
      ],
      recommended: false,
    },
  ];

  return (
    <div
      className="modal-overlay"
      onClick={onClose}
      role="dialog"
      aria-modal="true"
      aria-labelledby="plans-modal-title"
    >
      <div
        className="plans-modal-container"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="plans-modal-header">
          <div className="plans-header-title">
            <div className="plans-icon-badge">
              <Sparkles size={18} />
            </div>
            <div>
              <h2 id="plans-modal-title">Kirana Kavach Plans & Pricing</h2>
              <p>Choose the right copilot plan for your General Store</p>
            </div>
          </div>
          <button className="btn-modal-close" onClick={onClose} aria-label="Close modal">
            <X size={18} />
          </button>
        </div>

        <div className="plans-grid">
          {plans.map((plan) => {
            const isCurrent = currentPlan.toLowerCase() === plan.id.toLowerCase();
            return (
              <div
                key={plan.id}
                className={`plan-card ${plan.recommended ? "recommended" : ""} ${
                  isCurrent ? "current" : ""
                }`}
              >
                {plan.recommended && (
                  <div className="plan-badge-recommended">
                    <Crown size={12} /> MOST POPULAR
                  </div>
                )}
                <div className="plan-card-header">
                  <h3>{plan.name}</h3>
                  <p className="plan-desc">{plan.description}</p>
                  <div className="plan-price-row">
                    <span className="price-amount">{plan.price}</span>
                    <span className="price-period">{plan.period}</span>
                  </div>
                </div>

                <ul className="plan-features-list">
                  {plan.features.map((feature, idx) => (
                    <li key={idx}>
                      <Check size={15} className="check-icon" />
                      <span>{feature}</span>
                    </li>
                  ))}
                </ul>

                <button
                  className={`btn-plan-select ${
                    isCurrent
                      ? "btn-plan-current"
                      : plan.recommended
                      ? "btn-plan-primary"
                      : "btn-plan-secondary"
                  }`}
                  onClick={() => onSelectPlan(plan.id)}
                  disabled={isCurrent}
                >
                  {isCurrent ? "Current Plan" : `Choose ${plan.name}`}
                </button>
              </div>
            );
          })}
        </div>

        <div className="plans-modal-footer">
          <p className="demo-disclaimer-note">
            ℹ️ Plans shown are part of the Kirana Kavach demo experience. All features are active during this trial.
          </p>
        </div>
      </div>
    </div>
  );
};
