// Registry mapping the dataset's circuit_name (as returned by the API) to the
// real, FastF1-aligned circuit data fetched via tools/circuit-alignment/.
// See batch_align_all.py for how each of these was generated, and the
// alignment residual (~20-100px, documented per-circuit) for how precise the
// sector markers are for that specific track.
import austin from "./circuits/austin.json";
import bahrain from "./circuits/bahrain.json";
import baku from "./circuits/baku.json";
import catalunya from "./circuits/catalunya.json";
import hockenheimring from "./circuits/hockenheimring.json";
import hungaroring from "./circuits/hungaroring.json";
import imola from "./circuits/imola.json";
import interlagos from "./circuits/interlagos.json";
import istanbul from "./circuits/istanbul.json";
import jeddah from "./circuits/jeddah.json";
import lasVegas from "./circuits/las-vegas.json";
import lusail from "./circuits/lusail.json";
import marinaBay from "./circuits/marina-bay.json";
import melbourne from "./circuits/melbourne.json";
import mexicoCity from "./circuits/mexico-city.json";
import miami from "./circuits/miami.json";
import monaco from "./circuits/monaco.json";
import montreal from "./circuits/montreal.json";
import monza from "./circuits/monza.json";
import mugello from "./circuits/mugello.json";
import nurburgring from "./circuits/nurburgring.json";
import paulRicard from "./circuits/paul-ricard.json";
import portimao from "./circuits/portimao.json";
import shanghai from "./circuits/shanghai.json";
import silverstone from "./circuits/silverstone.json";
import sochi from "./circuits/sochi.json";
import spielberg from "./circuits/spielberg.json";
import suzuka from "./circuits/suzuka.json";
import yasMarina from "./circuits/yas-marina.json";
import zandvoort from "./circuits/zandvoort.json";
import { SPA_PATH_D, SPA_SECTOR_POINTS } from "./spaCircuit";

export interface CircuitData {
  slug: string;
  pathD: string;
  numCorners: number;
  residualPx: number;
  sectorPoints: [number, number][];
}

interface RawCircuitJson {
  slug: string;
  pathD: string;
  numCorners: number;
  residualPx: number;
  sectorPoints: number[][];
}

function normalize(raw: RawCircuitJson): CircuitData {
  return {
    slug: raw.slug,
    pathD: raw.pathD,
    numCorners: raw.numCorners,
    residualPx: raw.residualPx,
    sectorPoints: raw.sectorPoints.map(([x, y]) => [x, y]),
  };
}

const spa: CircuitData = {
  slug: "spa-francorchamps",
  pathD: SPA_PATH_D,
  numCorners: 19,
  residualPx: 36.9,
  sectorPoints: SPA_SECTOR_POINTS,
};

const BY_SLUG: Record<string, CircuitData> = {
  "spa-francorchamps": spa,
  austin: normalize(austin),
  bahrain: normalize(bahrain),
  baku: normalize(baku),
  catalunya: normalize(catalunya),
  hockenheimring: normalize(hockenheimring),
  hungaroring: normalize(hungaroring),
  imola: normalize(imola),
  interlagos: normalize(interlagos),
  istanbul: normalize(istanbul),
  jeddah: normalize(jeddah),
  "las-vegas": normalize(lasVegas),
  lusail: normalize(lusail),
  "marina-bay": normalize(marinaBay),
  melbourne: normalize(melbourne),
  "mexico-city": normalize(mexicoCity),
  miami: normalize(miami),
  monaco: normalize(monaco),
  montreal: normalize(montreal),
  monza: normalize(monza),
  mugello: normalize(mugello),
  nurburgring: normalize(nurburgring),
  "paul-ricard": normalize(paulRicard),
  portimao: normalize(portimao),
  shanghai: normalize(shanghai),
  silverstone: normalize(silverstone),
  sochi: normalize(sochi),
  spielberg: normalize(spielberg),
  suzuka: normalize(suzuka),
  "yas-marina": normalize(yasMarina),
  zandvoort: normalize(zandvoort),
};

// dataset circuit_name -> circuits.json slug. Ported from
// tools/circuit-alignment/batch_align_all.py's CIRCUIT_NAME_TO_SLUG — keep the
// two in sync if the dataset's circuit_name strings ever change.
// Circuits commented out have no real data: FastF1 doesn't reliably expose
// session_info for pre-2018 seasons (see batch_results.json for the failures).
const CIRCUIT_NAME_TO_SLUG: Record<string, string> = {
  "Albert Park Grand Prix Circuit": "melbourne",
  "Autodromo Enzo e Dino Ferrari": "imola",
  "Autodromo Internazionale del Mugello": "mugello",
  "Autodromo Nazionale di Monza": "monza",
  "Autódromo Hermanos Rodríguez": "mexico-city",
  "Autódromo Internacional do Algarve": "portimao",
  "Autódromo José Carlos Pace": "interlagos",
  "Bahrain International Circuit": "bahrain",
  "Baku City Circuit": "baku",
  // "Buddh International Circuit": no real data (2013, pre-FastF1-coverage)
  "Circuit Gilles Villeneuve": "montreal",
  "Circuit Park Zandvoort": "zandvoort",
  "Circuit Paul Ricard": "paul-ricard",
  "Circuit de Barcelona-Catalunya": "catalunya",
  "Circuit de Monaco": "monaco",
  "Circuit de Spa-Francorchamps": "spa-francorchamps",
  "Circuit of the Americas": "austin",
  Hockenheimring: "hockenheimring",
  Hungaroring: "hungaroring",
  "Istanbul Park": "istanbul",
  "Jeddah Corniche Circuit": "jeddah",
  // "Korean International Circuit": no real data (2013, pre-FastF1-coverage)
  "Las Vegas Strip Street Circuit": "las-vegas",
  "Losail International Circuit": "lusail",
  "Marina Bay Street Circuit": "marina-bay",
  "Miami International Autodrome": "miami",
  Nürburgring: "nurburgring",
  "Red Bull Ring": "spielberg",
  "Sepang International Circuit": "sepang", // no real data (2017, pre-FastF1-coverage) — kept for clarity, not in BY_SLUG
  "Shanghai International Circuit": "shanghai",
  "Silverstone Circuit": "silverstone",
  "Sochi Autodrom": "sochi",
  "Suzuka Circuit": "suzuka",
  // "Valencia Street Circuit": no real data (2012, pre-FastF1-coverage)
  "Yas Marina Circuit": "yas-marina",
};

export function getCircuitData(circuitName: string): CircuitData | null {
  const slug = CIRCUIT_NAME_TO_SLUG[circuitName];
  if (!slug) return null;
  return BY_SLUG[slug] ?? null;
}
