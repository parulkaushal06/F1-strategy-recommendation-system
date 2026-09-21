import Nav from "@/components/Nav";
import Footer from "@/components/Footer";
import results from "@/data/belgian_gp_2023_results.json";

const TEAM_COLORS: Record<string, string> = {
  "Red Bull": "#2246A8",
  Ferrari: "#C1121C",
  Mercedes: "#4DD9C4",
  "Aston Martin": "#1F7A5C",
  McLaren: "#E8792E",
  "Alpine F1 Team": "#2D6FE0",
  AlphaTauri: "#3A4A5C",
};

export default function Results() {
  return (
    <>
      <Nav active="/results" />

      <section className="max-w-[1280px] mx-auto px-6 md:px-10 pt-10 pb-6">
        <div className="eyebrow mb-3">RACE HISTORY</div>
        <h1 className="text-[32px] sm:text-[40px] md:text-[52px] leading-[0.95] mb-6">Belgian Grand Prix · 2023</h1>
        <div className="flex flex-wrap gap-2">
          {["2018", "2019", "2021", "2022"].map((year) => (
            <span key={year} className="btn !py-2 !px-3 opacity-50">
              {year}
            </span>
          ))}
          <span className="btn btn--accent !py-2 !px-3">2023</span>
        </div>
      </section>

      <section className="max-w-[1280px] mx-auto px-6 md:px-10 pb-16">
        <div className="card p-6">
          <div className="overflow-x-auto">
            <table className="w-full text-[13px]">
              <thead>
                <tr className="eyebrow text-left hairline-bottom">
                  <th className="py-2 pr-4 font-normal">POS</th>
                  <th className="py-2 pr-4 font-normal">DRIVER</th>
                  <th className="py-2 pr-4 font-normal">TEAM</th>
                  <th className="py-2 pr-4 font-normal text-right">TIME / GAP</th>
                  <th className="py-2 pr-4 font-normal text-right">PIT STOPS</th>
                  <th className="py-2 pr-4 font-normal text-right">FASTEST LAP</th>
                </tr>
              </thead>
              <tbody className="mono">
                {results.map((r, i, arr) => (
                  <tr key={r.position} className={i < arr.length - 1 ? "hairline-bottom" : ""}>
                    <td className="py-3 pr-4">{r.position}</td>
                    <td className="py-3 pr-4">
                      <span className="inline-flex items-center gap-2">
                        <i
                          className="w-2 h-2 rounded-full inline-block"
                          style={{ background: TEAM_COLORS[r.team] ?? "var(--ink-muted)" }}
                        />
                        {r.code} · {r.name}
                      </span>
                    </td>
                    <td className="py-3 pr-4 text-[color:var(--ink-secondary)]">{r.team}</td>
                    <td className="py-3 pr-4 text-right">{r.time}</td>
                    <td className="py-3 pr-4 text-right">{r.pitStops}</td>
                    <td className="py-3 pr-4 text-right">
                      {r.fastestLap && (
                        <span className="pill pill--purple">
                          <span className="dot" />
                          FASTEST
                        </span>
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      </section>

      <Footer />
    </>
  );
}