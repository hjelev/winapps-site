export class GitHubApiError extends Error {}

export interface GitHubClientOptions {
  owner: string;
  repo: string;
  baseBranch: string;
  token: string;
}

function arrayBufferToBase64(buffer: ArrayBuffer): string {
  const bytes = new Uint8Array(buffer);
  const chunkSize = 0x8000;
  let binary = "";
  for (let i = 0; i < bytes.length; i += chunkSize) {
    const chunk = bytes.subarray(i, i + chunkSize);
    binary += String.fromCharCode(...chunk);
  }
  return btoa(binary);
}

export class GitHubClient {
  private readonly owner: string;
  private readonly repo: string;
  private readonly baseBranch: string;
  private readonly token: string;

  constructor(options: GitHubClientOptions) {
    this.owner = options.owner;
    this.repo = options.repo;
    this.baseBranch = options.baseBranch;
    this.token = options.token;
  }

  private async request(path: string, init: RequestInit = {}): Promise<Response> {
    const response = await fetch(`https://api.github.com/repos/${this.owner}/${this.repo}${path}`, {
      ...init,
      headers: {
        Authorization: `Bearer ${this.token}`,
        Accept: "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
        "User-Agent": "winapps-submit-app-worker",
        ...(init.headers ?? {}),
      },
    });
    return response;
  }

  async getBaseBranchSha(): Promise<string> {
    const response = await this.request(`/git/ref/heads/${this.baseBranch}`);
    if (!response.ok) {
      throw new GitHubApiError(`Failed to read base branch ref (${response.status})`);
    }
    const data = (await response.json()) as { object: { sha: string } };
    return data.object.sha;
  }

  async slugTaken(slug: string): Promise<boolean> {
    const response = await this.request(
      `/contents/content/${slug}.html?ref=${encodeURIComponent(this.baseBranch)}`
    );
    if (response.status === 404) {
      return false;
    }
    if (!response.ok) {
      throw new GitHubApiError(`Failed to check slug availability (${response.status})`);
    }
    return true;
  }

  async createBranch(branchName: string, fromSha: string): Promise<void> {
    const response = await this.request("/git/refs", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ ref: `refs/heads/${branchName}`, sha: fromSha }),
    });
    if (!response.ok) {
      throw new GitHubApiError(`Failed to create branch ${branchName} (${response.status})`);
    }
  }

  async commitFile(params: {
    path: string;
    content: ArrayBuffer;
    branch: string;
    message: string;
  }): Promise<void> {
    const response = await this.request(`/contents/${params.path}`, {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        message: params.message,
        content: arrayBufferToBase64(params.content),
        branch: params.branch,
      }),
    });
    if (!response.ok) {
      throw new GitHubApiError(`Failed to commit ${params.path} (${response.status})`);
    }
  }

  async dispatch(eventType: string, clientPayload: Record<string, unknown>): Promise<void> {
    const response = await this.request("/dispatches", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ event_type: eventType, client_payload: clientPayload }),
    });
    if (!response.ok) {
      throw new GitHubApiError(`Failed to dispatch ${eventType} (${response.status})`);
    }
  }
}
