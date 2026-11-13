import { useState } from "react";
import { CompanyHome } from "./CompanyHome";
import { NAV } from "./nav";

export function App() {
  const [section, setSection] = useState<(typeof NAV)[number]>("Company");
  return (
    <main>
      <nav aria-label="Sections">
        {NAV.map((name) => (
          <button key={name} type="button" onClick={() => setSection(name)}>
            {name}
          </button>
        ))}
      </nav>
      {section === "Company" ? <CompanyHome /> : <h1>{section}</h1>}
    </main>
  );
}
