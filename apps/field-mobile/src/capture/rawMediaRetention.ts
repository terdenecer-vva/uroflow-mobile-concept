export type RuntimeRecordingHandle = {
  stop: () => Promise<void>;
  uri: string | null;
};

export type RuntimeRecordingCleanupResult = {
  stopped: boolean;
  deletedUri: string | null;
  stopFailed: boolean;
  deleteFailed: boolean;
};

export type DeleteRuntimeRecordingFile = (uri: string) => Promise<void> | void;

export async function deleteRuntimeRecordingFile(uri: string): Promise<void> {
  const { File } = await import("expo-file-system");
  new File(uri).delete();
}

export async function stopAndDeleteRuntimeRecording(
  recording: RuntimeRecordingHandle,
  deleteFile: DeleteRuntimeRecordingFile = deleteRuntimeRecordingFile,
): Promise<RuntimeRecordingCleanupResult> {
  const uriBeforeStop = recording.uri;
  let stopFailed = false;

  try {
    await recording.stop();
  } catch {
    stopFailed = true;
  }

  const deletedUri = recording.uri || uriBeforeStop;
  let deleteFailed = false;
  if (deletedUri) {
    try {
      await deleteFile(deletedUri);
    } catch {
      deleteFailed = true;
    }
  }

  return {
    stopped: !stopFailed,
    deletedUri,
    stopFailed,
    deleteFailed,
  };
}
