import { Container } from "@cloudflare/containers";
import { env } from "cloudflare:workers";

export class DiguesAppContainer extends Container {
  defaultPort = 8000;
  sleepAfter = "10m";

  envVars = {
    DATABASE_URL: env.DATABASE_URL,
    MISTRAL_API_KEY: env.MISTRAL_API_KEY,
    METEOFRANCE_API_KEY: env.METEOFRANCE_API_KEY,
  };
}

interface Env {
  DIGUES_APP: DurableObjectNamespace<DiguesAppContainer>;
  DATABASE_URL: string;
  MISTRAL_API_KEY: string;
  METEOFRANCE_API_KEY: string;
}

export default {
  async fetch(request: Request, env: Env): Promise<Response> {
    const container = env.DIGUES_APP.getByName("main");
    return container.fetch(request);
  },
};
