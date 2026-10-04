import { readFile } from "node:fs/promises";
import path from "node:path";

import { z } from "zod";

import { frontendDataSchema } from "../schemas/frontend-data";
import type { FrontendData } from "../types/solar";

const MOCK_FIXTURE_RELATIVE_PATH = [
  "data",
  "mock",
  "sample_full_frontend_data.json",
] as const;

export class FrontendDataLoadError extends Error {
  readonly details?: string;

  constructor(message: string, details?: string) {
    super(message);
    this.name = "FrontendDataLoadError";
    this.details = details;
  }
}

export type FrontendDataLoadResult =
  | {
      ok: true;
      data: FrontendData;
      sourcePath: string;
    }
  | {
      ok: false;
      error: FrontendDataLoadError;
    };

/** Set to a JSON file (absolute, or relative to the repository root) to show a generated run instead of the mock fixture. */
export const FRONTEND_DATA_PATH_VARIABLE = "SOLAR_FRONTEND_DATA";

/** The payload file the app shows: the configured generated run when one is set, otherwise the mock fixture. */
export function resolveFrontendDataPath(
  environment: Record<string, string | undefined> = process.env,
): string {
  const configured = environment[FRONTEND_DATA_PATH_VARIABLE]?.trim();
  if (!configured) {
    return resolveMockFrontendDataPath();
  }
  return path.isAbsolute(configured)
    ? configured
    : path.resolve(process.cwd(), "..", configured);
}

export function resolveMockFrontendDataPath(): string {
  // npm commands are run from /frontend. Keeping the fixture in /data avoids
  // duplicating the shared contract inside the web app.
  return path.resolve(
    process.cwd(),
    "..",
    ...MOCK_FIXTURE_RELATIVE_PATH,
  );
}

export async function parseFrontendData(
  raw: unknown,
): Promise<FrontendData> {
  try {
    return frontendDataSchema.parse(raw);
  } catch (error) {
    if (error instanceof z.ZodError) {
      const details = error.issues
        .map((issue) => {
          const location =
            issue.path.length > 0 ? issue.path.join(".") : "payload";
          return `${location}: ${issue.message}`;
        })
        .join("\n");

      throw new FrontendDataLoadError(
        "SolarAI frontend data failed contract validation.",
        details,
      );
    }

    throw error;
  }
}

export async function loadFrontendData(
  filePath = resolveMockFrontendDataPath(),
): Promise<FrontendData> {
  let text: string;

  try {
    text = await readFile(filePath, "utf8");
  } catch (error) {
    throw new FrontendDataLoadError(
      "SolarAI frontend data file could not be read.",
      error instanceof Error ? error.message : String(error),
    );
  }

  let raw: unknown;

  try {
    raw = JSON.parse(text) as unknown;
  } catch (error) {
    throw new FrontendDataLoadError(
      "SolarAI frontend data contains invalid JSON.",
      error instanceof Error ? error.message : String(error),
    );
  }

  return parseFrontendData(raw);
}

export async function loadFrontendDataResult(
  filePath = resolveFrontendDataPath(),
): Promise<FrontendDataLoadResult> {
  try {
    return {
      ok: true,
      data: await loadFrontendData(filePath),
      sourcePath: filePath,
    };
  } catch (error) {
    if (error instanceof FrontendDataLoadError) {
      return {
        ok: false,
        error,
      };
    }

    return {
      ok: false,
      error: new FrontendDataLoadError(
        "Unexpected error while loading SolarAI frontend data.",
        error instanceof Error ? error.message : String(error),
      ),
    };
  }
}
