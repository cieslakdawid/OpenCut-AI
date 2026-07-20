import { toast } from "sonner";
import { Input, ALL_FORMATS, BlobSource } from "mediabunny";

const AI_BACKEND_URL =
	process.env.NEXT_PUBLIC_AI_BACKEND_URL || "http://localhost:8420";

/**
 * Ensure a video file can be decoded by the browser.
 *
 * The editor decodes video with the browser's WebCodecs decoder, which has no
 * support for professional codecs like Apple ProRes ('apch'). When the primary
 * video track reports it can't be decoded, this uploads the file to the AI
 * backend, which re-encodes it to H.264/AAC MP4 with FFmpeg, and returns the
 * converted File. Files that are already decodable (or have no video track) are
 * returned unchanged.
 */
export async function ensureDecodableVideo(file: File): Promise<File> {
	let needsTranscode = false;

	try {
		const input = new Input({
			source: new BlobSource(file),
			formats: ALL_FORMATS,
		});
		const track = await input.getPrimaryVideoTrack();
		if (!track) {
			// No video track (e.g. audio-only) — nothing to transcode here.
			return file;
		}
		needsTranscode = !(await track.canDecode());
	} catch {
		// Couldn't parse in-browser at all; let the backend attempt a convert.
		needsTranscode = true;
	}

	if (!needsTranscode) {
		return file;
	}

	const toastId = toast.loading(
		`Converting "${file.name}" to a supported format…`,
	);

	try {
		const form = new FormData();
		form.append("file", file, file.name);

		const response = await fetch(`${AI_BACKEND_URL}/api/media/transcode`, {
			method: "POST",
			body: form,
		});

		if (!response.ok) {
			throw new Error(`Transcode request failed (${response.status})`);
		}

		const blob = await response.blob();
		const baseName = file.name.replace(/\.[^./\\]+$/, "");
		const converted = new File([blob], `${baseName}.mp4`, {
			type: "video/mp4",
		});

		toast.success(`Converted "${file.name}"`, { id: toastId });
		return converted;
	} catch (error) {
		toast.error(
			`Could not convert "${file.name}". Make sure the AI backend is reachable.`,
			{ id: toastId },
		);
		throw error;
	}
}
