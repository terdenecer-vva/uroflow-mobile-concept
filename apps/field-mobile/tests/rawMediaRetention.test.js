const assert = require("node:assert/strict");
const path = require("node:path");
const test = require("node:test");

const buildDir = process.env.MOBILE_UNIT_BUILD_DIR ?? "/tmp/uroflow-field-mobile-unit";
const retention = require(path.join(buildDir, "capture/rawMediaRetention.js"));

test("stopAndDeleteRuntimeRecording deletes recorder uri after stop", async () => {
  const deleted = [];
  const recording = {
    uri: "file:///tmp/runtime-recording.m4a",
    async stop() {
      this.uri = "file:///tmp/runtime-recording-final.m4a";
    },
  };

  const result = await retention.stopAndDeleteRuntimeRecording(recording, async (uri) => {
    deleted.push(uri);
  });

  assert.deepEqual(deleted, ["file:///tmp/runtime-recording-final.m4a"]);
  assert.deepEqual(result, {
    stopped: true,
    deletedUri: "file:///tmp/runtime-recording-final.m4a",
    stopFailed: false,
    deleteFailed: false,
  });
});

test("stopAndDeleteRuntimeRecording still deletes pre-stop uri when stop fails", async () => {
  const deleted = [];
  const recording = {
    uri: "file:///tmp/runtime-recording-prestop.m4a",
    async stop() {
      throw new Error("already stopped");
    },
  };

  const result = await retention.stopAndDeleteRuntimeRecording(recording, (uri) => {
    deleted.push(uri);
  });

  assert.deepEqual(deleted, ["file:///tmp/runtime-recording-prestop.m4a"]);
  assert.deepEqual(result, {
    stopped: false,
    deletedUri: "file:///tmp/runtime-recording-prestop.m4a",
    stopFailed: true,
    deleteFailed: false,
  });
});

test("stopAndDeleteRuntimeRecording reports best-effort delete failure", async () => {
  const recording = {
    uri: "file:///tmp/runtime-recording-delete-fails.m4a",
    async stop() {},
  };

  const result = await retention.stopAndDeleteRuntimeRecording(recording, () => {
    throw new Error("delete failed");
  });

  assert.deepEqual(result, {
    stopped: true,
    deletedUri: "file:///tmp/runtime-recording-delete-fails.m4a",
    stopFailed: false,
    deleteFailed: true,
  });
});
