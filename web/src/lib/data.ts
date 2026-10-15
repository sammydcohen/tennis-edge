import "server-only";
import fs from "node:fs";
import path from "node:path";

import type {
  CalibrationPoint,
  ClvRow,
  EdgeBucket,
  Equity,
  RankedPlayer,
  Segments,
  Summary,
  Tour,
} from "./types";

// Written by `python -m tennis_edge.export`; read at build time.
function read<T>(name: string): T {
  const file = path.join(process.cwd(), "public", "data", `${name}.json`);
  return JSON.parse(fs.readFileSync(file, "utf8")) as T;
}

export const getSummary = () => read<Summary>("summary");
export const getSegments = () => read<Segments>("segments");
export const getClv = () => read<ClvRow[]>("clv");
export const getEquity = (tour: Tour) => read<Equity>(`${tour}_equity`);
export const getEdgeBuckets = (tour: Tour) => read<EdgeBucket[]>(`${tour}_edge_buckets`);
export const getCalibration = (tour: Tour) => read<CalibrationPoint[]>(`${tour}_calibration`);
export const getRankings = (tour: Tour) => read<RankedPlayer[]>(`${tour}_rankings`);
