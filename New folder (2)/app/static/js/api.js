class ApiClient {
  constructor() {
    this.csrfToken = "";
  }

  setCsrf(token) {
    this.csrfToken = token || "";
  }

  async request(path, options = {}) {
    const method = (options.method || "GET").toUpperCase();
    const headers = new Headers(options.headers || {});
    headers.set("Accept", "application/json");
    if (options.body && !(options.body instanceof FormData)) {
      headers.set("Content-Type", "application/json");
    }
    if (!["GET", "HEAD", "OPTIONS"].includes(method) && this.csrfToken) {
      headers.set("X-CSRF-Token", this.csrfToken);
    }

    let response;
    try {
      response = await fetch(path, { ...options, method, headers, credentials: "same-origin" });
    } catch (_error) {
      throw new ApiError("ارتباط با سرور برقرار نشد.", 0);
    }

    const data = await response.json().catch(() => ({}));
    if (!response.ok) {
      if (response.status === 401 && path !== "/api/auth/login") {
        document.dispatchEvent(new CustomEvent("auth:expired"));
      }
      throw new ApiError(data.error || "خطایی در سرور رخ داد.", response.status, data);
    }
    return data;
  }

  get(path) { return this.request(path); }
  post(path, payload = {}) { return this.request(path, { method: "POST", body: JSON.stringify(payload) }); }
  patch(path, payload = {}) { return this.request(path, { method: "PATCH", body: JSON.stringify(payload) }); }
  delete(path) { return this.request(path, { method: "DELETE" }); }
}

export class ApiError extends Error {
  constructor(message, status, data = {}) {
    super(message);
    this.name = "ApiError";
    this.status = status;
    this.data = data;
  }
}

export const api = new ApiClient();

