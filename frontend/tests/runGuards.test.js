import test from "node:test";
import assert from "node:assert/strict";
import { isCurrentRun, isCurrentRefresh } from "../src/runGuards.js";

test("polling accepts the active run", () => {
  assert.equal(isCurrentRun("run-current", "run-current"), true);
});

test("polling rejects a response from an older run", () => {
  assert.equal(isCurrentRun("run-new", "run-old"), false);
});

test("polling rejects a cancelled effect", () => {
  assert.equal(isCurrentRun("run-current", "run-current", true), false);
});

test("refresh accepts the active run and latest generation", () => {
  assert.equal(isCurrentRefresh("run-1", "run-1", 7, 7), true);
});

test("refresh rejects a response from an older run", () => {
  assert.equal(isCurrentRefresh("run-2", "run-1", 7, 7), false);
});

test("refresh rejects an older overlapping refresh", () => {
  assert.equal(isCurrentRefresh("run-1", "run-1", 8, 7), false);
});
