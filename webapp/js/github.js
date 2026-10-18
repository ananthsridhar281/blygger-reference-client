// GitHub committer: atomically commit a { path: contents } map to a repo via the Git Data
// API (blobs -> tree -> commit -> update ref). Pure static; talks only to api.github.com.
const API = "https://api.github.com";

async function gh(path, { pat, method = "GET", body } = {}) {
  const res = await fetch(API + path, {
    method,
    headers: {
      Authorization: `Bearer ${pat}`,
      Accept: "application/vnd.github+json",
      "X-GitHub-Api-Version": "2022-11-28",
      ...(body ? { "Content-Type": "application/json" } : {}),
    },
    body: body ? JSON.stringify(body) : undefined,
  });
  const text = await res.text();
  let data;
  try { data = JSON.parse(text); } catch { data = text; }
  if (!res.ok) {
    const msg = (data && data.message) || res.statusText;
    const err = new Error(`GitHub ${res.status}: ${msg}`);
    err.status = res.status;
    throw err;
  }
  return data;
}

function utf8Base64(str) {
  const bytes = new TextEncoder().encode(str);
  let bin = "";
  for (const b of bytes) bin += String.fromCharCode(b);
  return btoa(bin);
}

export async function testConnection({ owner, repo, pat }) {
  const r = await gh(`/repos/${owner}/${repo}`, { pat });
  return { fullName: r.full_name, permissions: r.permissions, defaultBranch: r.default_branch };
}

export async function commitFiles(files, { owner, repo, branch = "main", basePath = "", pat },
                                  message) {
  const prefix = basePath ? basePath.replace(/\/+$/, "") + "/" : "";

  // Create a blob per file.
  const tree = [];
  for (const [path, contents] of Object.entries(files)) {
    const blob = await gh(`/repos/${owner}/${repo}/git/blobs`, {
      pat, method: "POST", body: { content: utf8Base64(contents), encoding: "base64" },
    });
    tree.push({ path: prefix + path, mode: "100644", type: "blob", sha: blob.sha });
  }

  // Resolve the branch head (may not exist on a brand-new, empty repo).
  let baseCommitSha = null;
  let baseTreeSha = undefined;
  let refExists = true;
  try {
    const ref = await gh(`/repos/${owner}/${repo}/git/ref/heads/${branch}`, { pat });
    baseCommitSha = ref.object.sha;
    const baseCommit = await gh(`/repos/${owner}/${repo}/git/commits/${baseCommitSha}`, { pat });
    baseTreeSha = baseCommit.tree.sha;
  } catch (e) {
    if (e.status === 404 || e.status === 409) refExists = false; else throw e;
  }

  const newTree = await gh(`/repos/${owner}/${repo}/git/trees`, {
    pat, method: "POST",
    body: baseTreeSha ? { base_tree: baseTreeSha, tree } : { tree },
  });
  const commit = await gh(`/repos/${owner}/${repo}/git/commits`, {
    pat, method: "POST",
    body: { message, tree: newTree.sha, parents: baseCommitSha ? [baseCommitSha] : [] },
  });

  if (refExists) {
    await gh(`/repos/${owner}/${repo}/git/refs/heads/${branch}`, {
      pat, method: "PATCH", body: { sha: commit.sha },
    });
  } else {
    await gh(`/repos/${owner}/${repo}/git/refs`, {
      pat, method: "POST", body: { ref: `refs/heads/${branch}`, sha: commit.sha },
    });
  }

  return {
    sha: commit.sha,
    commitUrl: commit.html_url || `https://github.com/${owner}/${repo}/commit/${commit.sha}`,
  };
}
