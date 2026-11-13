import { useState } from "react";
import { LANES } from "./nav";

const companyId = import.meta.env.VITE_COMPANY_ID as string | undefined;
const apiBase = (import.meta.env.VITE_API_BASE as string | undefined) ?? "";

export function CompanyHome() {
  const [left, setLeft] = useState(42);

  function remember(next: number) {
    setLeft(next);
    if (!companyId) {
      return;
    }
    void fetch(`${apiBase}/api/v1/companies/${companyId}/preferences/home.splitter`, {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ value: [next, 100 - next] }),
    });
  }

  return (
    <div className="home" style={{ display: "flex", minHeight: "70vh" }}>
      <section style={{ width: `${left}%` }} aria-label="Workflow lanes">
        {LANES.map((title) => (
          <p key={title} data-lane={title}>
            {title}
          </p>
        ))}
      </section>
      <input
        aria-label="Resize chart"
        type="range"
        min={20}
        max={70}
        value={left}
        onChange={(event) => remember(Number(event.target.value))}
      />
      <section style={{ flex: 1 }} aria-label="Chart of accounts">
        <h2>Chart of accounts</h2>
      </section>
    </div>
  );
}
