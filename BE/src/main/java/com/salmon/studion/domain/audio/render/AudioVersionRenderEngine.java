package com.salmon.studion.domain.audio.render;

import com.salmon.studion.domain.audio.render.dto.AudioVersionRenderResult;
import com.salmon.studion.domain.audio.render.dto.AudioVersionRenderSnapshot;
import com.salmon.studion.global.common.enums.MimeType;
import com.salmon.studion.global.common.response.ErrorCode;
import com.salmon.studion.global.exception.BusinessException;
import com.salmon.studion.global.infrastructure.cdn.CdnUrlService;
import lombok.RequiredArgsConstructor;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.stereotype.Component;

import java.io.IOException;
import java.net.URI;
import java.net.http.HttpClient;
import java.net.http.HttpRequest;
import java.net.http.HttpResponse;
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.nio.file.Path;
import java.time.Duration;
import java.util.ArrayList;
import java.util.Comparator;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Locale;
import java.util.Map;
import java.util.stream.Collectors;

@Component
@RequiredArgsConstructor
public class AudioVersionRenderEngine {

    private final CdnUrlService cdnUrlService;

    @Value("${app.audio-version.ffmpeg-binary:ffmpeg}")
    private String ffmpegBinary;

    public AudioVersionRenderResult render(AudioVersionRenderSnapshot snapshot, String versionName) {
        Path workingDirectory = createWorkingDirectory(snapshot.getProjectId());

        try {
            Map<String, Path> sourceFilesByObjectKey = downloadSourceFiles(snapshot, workingDirectory);
            Path outputPath = renderWithFfmpeg(snapshot, versionName, workingDirectory, sourceFilesByObjectKey);
            return AudioVersionRenderResult.of(
                    outputPath,
                    MimeType.MPEG,
                    sanitizeOriginalFileName(versionName) + ".mp3",
                    snapshot.getRenderDurationMs()
            );
        } catch (InterruptedException exception) {
            Thread.currentThread().interrupt();
            throw new BusinessException(ErrorCode.AUDIO_UPLOAD_FAILED, "오디오 버전 렌더링에 실패했습니다.");
        } catch (IOException exception) {
            throw new BusinessException(ErrorCode.AUDIO_UPLOAD_FAILED, "오디오 버전 렌더링에 실패했습니다.");
        }
    }

    public void cleanupWorkingDirectory(Path workingDirectory) {
        if (workingDirectory == null) {
            return;
        }

        try (var walk = Files.walk(workingDirectory)) {
            walk.sorted(Comparator.reverseOrder())
                    .forEach(path -> {
                        try {
                            Files.deleteIfExists(path);
                        } catch (IOException ignored) {
                        }
                    });
        } catch (IOException ignored) {
        }
    }

    private Path createWorkingDirectory(Integer projectId) {
        try {
            return Files.createTempDirectory("audio-version-" + projectId + "-");
        } catch (IOException exception) {
            throw new BusinessException(ErrorCode.INTERNAL_SERVER_ERROR, "오디오 버전 임시 디렉터리 생성에 실패했습니다.");
        }
    }

    private Map<String, Path> downloadSourceFiles(
            AudioVersionRenderSnapshot snapshot,
            Path workingDirectory
    ) throws IOException, InterruptedException {
        HttpClient httpClient = HttpClient.newBuilder()
                .connectTimeout(Duration.ofSeconds(10))
                .build();

        Map<String, Path> sourceFilesByObjectKey = new LinkedHashMap<>();
        for (AudioVersionRenderSnapshot.RenderClip clip : snapshot.getClips()) {
            if (sourceFilesByObjectKey.containsKey(clip.getObjectKey())) {
                continue;
            }

            String fileExtension = extractExtension(clip.getOriginalName());
            Path sourcePath = workingDirectory.resolve("source-" + clip.getAudioMetadataId() + "." + fileExtension);
            HttpRequest request = HttpRequest.newBuilder()
                    .GET()
                    .uri(URI.create(cdnUrlService.createAudioUrl(clip.getObjectKey())))
                    .timeout(Duration.ofSeconds(30))
                    .build();

            HttpResponse<Path> response = httpClient.send(
                    request,
                    HttpResponse.BodyHandlers.ofFile(sourcePath)
            );

            if (response.statusCode() >= 400) {
                throw new BusinessException(ErrorCode.AUDIO_DOWNLOAD_FAILED, "원본 오디오 파일 다운로드에 실패했습니다.");
            }

            sourceFilesByObjectKey.put(clip.getObjectKey(), sourcePath);
        }

        return sourceFilesByObjectKey;
    }

    private Path renderWithFfmpeg(
            AudioVersionRenderSnapshot snapshot,
            String versionName,
            Path workingDirectory,
            Map<String, Path> sourceFilesByObjectKey
    ) throws IOException, InterruptedException {
        Path outputPath = workingDirectory.resolve(sanitizeOriginalFileName(versionName) + ".mp3");
        Path filterScriptPath = workingDirectory.resolve("filter_complex.txt");

        List<String> command = new ArrayList<>();
        command.add(ffmpegBinary);
        command.add("-y");

        List<AudioVersionRenderSnapshot.RenderClip> clips = snapshot.getClips();
        if (clips.isEmpty()) {
            command.add("-f");
            command.add("lavfi");
            command.add("-i");
            command.add("anullsrc=r=44100:cl=stereo");

            double durationSeconds = snapshot.getRenderDurationMs() / 1000.0d;
            command.add("-t");
            command.add(formatSeconds(durationSeconds));
            command.add("-c:a");
            command.add("libmp3lame");
            command.add("-b:a");
            command.add("192k");
            command.add(outputPath.toString());
            executeFfmpeg(command, workingDirectory);
            return outputPath;
        }

        for (AudioVersionRenderSnapshot.RenderClip clip : clips) {
            Path sourcePath = sourceFilesByObjectKey.get(clip.getObjectKey());
            if (sourcePath == null) {
                throw new BusinessException(ErrorCode.AUDIO_FILE_NOT_FOUND);
            }
            command.add("-i");
            command.add(sourcePath.toString());
        }

        String filterScript = buildFilterScript(snapshot);
        Files.writeString(filterScriptPath, filterScript, StandardCharsets.UTF_8);

        command.add("-filter_complex_script");
        command.add(filterScriptPath.toString());
        command.add("-map");
        command.add("[master_out]");
        command.add("-c:a");
        command.add("libmp3lame");
        command.add("-b:a");
        command.add("192k");
        command.add(outputPath.toString());

        executeFfmpeg(command, workingDirectory);
        return outputPath;
    }

    private void executeFfmpeg(List<String> command, Path workingDirectory) throws IOException, InterruptedException {
        ProcessBuilder processBuilder = new ProcessBuilder(command);
        processBuilder.directory(workingDirectory.toFile());
        processBuilder.redirectErrorStream(true);
        Process process = processBuilder.start();
        String output = new String(process.getInputStream().readAllBytes(), StandardCharsets.UTF_8);
        int exitCode = process.waitFor();

        if (exitCode != 0) {
            throw new BusinessException(ErrorCode.FAIL, "ffmpeg 렌더링에 실패했습니다. " + trimFailureMessage(output));
        }
    }

    private String buildFilterScript(AudioVersionRenderSnapshot snapshot) {
        StringBuilder builder = new StringBuilder();

        Map<Integer, List<AudioVersionRenderSnapshot.RenderClip>> clipsByTrackId = snapshot.getClips().stream()
                .collect(Collectors.groupingBy(
                        AudioVersionRenderSnapshot.RenderClip::getTrackId,
                        LinkedHashMap::new,
                        Collectors.toList()
                ));

        Map<Integer, AudioVersionRenderSnapshot.RenderTrackEq> trackEqByTrackId = snapshot.getTrackEqs().stream()
                .collect(Collectors.toMap(
                        AudioVersionRenderSnapshot.RenderTrackEq::getTrackId,
                        trackEq -> trackEq,
                        (left, right) -> left,
                        LinkedHashMap::new
                ));

        List<String> trackOutputLabels = new ArrayList<>();
        for (int inputIndex = 0; inputIndex < snapshot.getClips().size(); inputIndex++) {
            AudioVersionRenderSnapshot.RenderClip clip = snapshot.getClips().get(inputIndex);
            String clipOutputLabel = "clip_" + clip.getClipId();
            builder.append("[").append(inputIndex).append(":a]")
                    .append("atrim=start=").append(formatSeconds(clip.getAudioStartMs() / 1000.0d))
                    .append(":duration=").append(formatSeconds(clip.getAudioDurationMs() / 1000.0d))
                    .append(",asetpts=PTS-STARTPTS")
                    .append(",aformat=sample_rates=44100:channel_layouts=stereo")
                    .append(",adelay=").append(clip.getTimelineStartMs()).append("|").append(clip.getTimelineStartMs())
                    .append("[").append(clipOutputLabel).append("];")
                    .append(System.lineSeparator());
        }

        for (AudioVersionRenderSnapshot.RenderTrack track : snapshot.getTracks()) {
            if (!Boolean.TRUE.equals(track.getRenderEnabled())) {
                continue;
            }

            List<AudioVersionRenderSnapshot.RenderClip> trackClips = clipsByTrackId.getOrDefault(track.getTrackId(), List.of());
            if (trackClips.isEmpty()) {
                continue;
            }

            String mixedTrackLabel = "track_" + track.getTrackId() + "_mix";
            String mixedTrackInputs = trackClips.stream()
                    .map(clip -> "[clip_" + clip.getClipId() + "]")
                    .collect(Collectors.joining());

            if (trackClips.size() == 1) {
                builder.append(mixedTrackInputs)
                        .append("anull[").append(mixedTrackLabel).append("];")
                        .append(System.lineSeparator());
            } else {
                builder.append(mixedTrackInputs)
                        .append("amix=inputs=").append(trackClips.size()).append(":normalize=0")
                        .append("[").append(mixedTrackLabel).append("];")
                        .append(System.lineSeparator());
            }

            String processedTrackLabel = appendTrackFilters(
                    builder,
                    mixedTrackLabel,
                    track,
                    trackEqByTrackId.get(track.getTrackId())
            );
            trackOutputLabels.add("[" + processedTrackLabel + "]");
        }

        if (trackOutputLabels.isEmpty()) {
            builder.append("anullsrc=r=44100:cl=stereo:d=")
                    .append(formatSeconds(snapshot.getRenderDurationMs() / 1000.0d))
                    .append("[mix_out];")
                    .append(System.lineSeparator());
        } else if (trackOutputLabels.size() == 1) {
            builder.append(trackOutputLabels.getFirst())
                    .append("anull[mix_out];")
                    .append(System.lineSeparator());
        } else {
            builder.append(String.join("", trackOutputLabels))
                    .append("amix=inputs=").append(trackOutputLabels.size()).append(":normalize=0")
                    .append("[mix_out];")
                    .append(System.lineSeparator());
        }

        appendMasterFilters(builder, snapshot.getMasterLimiter(), snapshot.getRenderDurationMs());
        return builder.toString();
    }

    private String appendTrackFilters(
            StringBuilder builder,
            String inputLabel,
            AudioVersionRenderSnapshot.RenderTrack track,
            AudioVersionRenderSnapshot.RenderTrackEq trackEq
    ) {
        String currentLabel = inputLabel;
        int stageIndex = 0;

        if (track.getVolume() != null && Math.abs(track.getVolume()) > 0.0001d) {
            String nextLabel = "track_" + track.getTrackId() + "_stage_" + stageIndex++;
            builder.append("[").append(currentLabel).append("]")
                    .append("volume=").append(formatDb(track.getVolume()))
                    .append("[").append(nextLabel).append("];")
                    .append(System.lineSeparator());
            currentLabel = nextLabel;
        }

        if (track.getPan() != null && track.getPan() != 0) {
            String nextLabel = "track_" + track.getTrackId() + "_stage_" + stageIndex++;
            double panRatio = Math.max(-1.0d, Math.min(1.0d, track.getPan() / 100.0d));
            double leftGain = panRatio >= 0 ? 1.0d - panRatio : 1.0d;
            double rightGain = panRatio >= 0 ? 1.0d : 1.0d + panRatio;

            builder.append("[").append(currentLabel).append("]")
                    .append("pan=stereo|c0=")
                    .append(formatPlain(leftGain)).append("*c0|c1=")
                    .append(formatPlain(rightGain)).append("*c1")
                    .append("[").append(nextLabel).append("];")
                    .append(System.lineSeparator());
            currentLabel = nextLabel;
        }

        if (trackEq != null) {
            for (AudioVersionRenderSnapshot.RenderEqBand band : trackEq.getBands()) {
                String nextLabel = "track_" + track.getTrackId() + "_stage_" + stageIndex++;
                builder.append("[").append(currentLabel).append("]")
                        .append(toEqFilter(band))
                        .append("[").append(nextLabel).append("];")
                        .append(System.lineSeparator());
                currentLabel = nextLabel;
            }
        }

        String outputLabel = "track_" + track.getTrackId() + "_out";
        builder.append("[").append(currentLabel).append("]")
                .append("anull[").append(outputLabel).append("];")
                .append(System.lineSeparator());
        return outputLabel;
    }

    private void appendMasterFilters(
            StringBuilder builder,
            AudioVersionRenderSnapshot.RenderMasterLimiter masterLimiter,
            Integer renderDurationMs
    ) {
        String currentLabel = "mix_out";
        int stageIndex = 0;

        if (masterLimiter != null && masterLimiter.getInputGainDb() != null && Math.abs(masterLimiter.getInputGainDb()) > 0.0001d) {
            String nextLabel = "master_stage_" + stageIndex++;
            builder.append("[").append(currentLabel).append("]")
                    .append("volume=").append(formatDb(masterLimiter.getInputGainDb()))
                    .append("[").append(nextLabel).append("];")
                    .append(System.lineSeparator());
            currentLabel = nextLabel;
        }

        if (masterLimiter != null && Boolean.TRUE.equals(masterLimiter.getIsEnabled())) {
            String nextLabel = "master_stage_" + stageIndex++;
            double limitLinear = Math.pow(10.0d, safeNumber(masterLimiter.getCeilingDbfs()) / 20.0d);
            builder.append("[").append(currentLabel).append("]")
                    .append("alimiter=limit=").append(formatPlain(limitLinear))
                    .append(":attack=").append(formatPlain(safeNumber(masterLimiter.getAttackMs())))
                    .append(":release=").append(formatPlain(safeNumber(masterLimiter.getReleaseMs())))
                    .append("[").append(nextLabel).append("];")
                    .append(System.lineSeparator());
            currentLabel = nextLabel;
        }

        if (masterLimiter != null && masterLimiter.getMakeupGainDb() != null && Math.abs(masterLimiter.getMakeupGainDb()) > 0.0001d) {
            String nextLabel = "master_stage_" + stageIndex++;
            builder.append("[").append(currentLabel).append("]")
                    .append("volume=").append(formatDb(masterLimiter.getMakeupGainDb()))
                    .append("[").append(nextLabel).append("];")
                    .append(System.lineSeparator());
            currentLabel = nextLabel;
        }

        builder.append("[").append(currentLabel).append("]")
                .append("atrim=duration=")
                .append(formatSeconds(renderDurationMs / 1000.0d))
                .append("[master_out];")
                .append(System.lineSeparator());
    }

    private String toEqFilter(AudioVersionRenderSnapshot.RenderEqBand band) {
        String eqType = band.getEqType();
        if ("LOW_SHELF".equals(eqType)) {
            return "bass=g=" + formatPlain(safeNumber(band.getGainDeltaDb()))
                    + ":f=" + band.getFrequencyHz();
        }
        if ("HIGH_SHELF".equals(eqType)) {
            return "treble=g=" + formatPlain(safeNumber(band.getGainDeltaDb()))
                    + ":f=" + band.getFrequencyHz();
        }
        return "equalizer=f=" + band.getFrequencyHz()
                + ":width_type=q:width=" + formatPlain(safeNumber(band.getQ()))
                + ":g=" + formatPlain(safeNumber(band.getGainDeltaDb()));
    }

    private String formatDb(Double value) {
        return formatPlain(value) + "dB";
    }

    private String formatSeconds(double seconds) {
        return formatPlain(seconds);
    }

    private String formatPlain(double value) {
        return String.format(Locale.US, "%.6f", value);
    }

    private double safeNumber(Double value) {
        return value == null ? 0.0d : value;
    }

    private String sanitizeOriginalFileName(String versionName) {
        String sanitized = versionName == null ? "audio-version" : versionName.trim();
        if (sanitized.isBlank()) {
            sanitized = "audio-version";
        }
        return sanitized.replaceAll("[\\\\/:*?\"<>|]", "_");
    }

    private String extractExtension(String originalName) {
        if (originalName == null || !originalName.contains(".")) {
            return "bin";
        }
        return originalName.substring(originalName.lastIndexOf('.') + 1);
    }

    private String trimFailureMessage(String output) {
        if (output == null || output.isBlank()) {
            return "";
        }
        String normalized = output.replaceAll("\\s+", " ").trim();
        if (normalized.length() <= 300) {
            return normalized;
        }
        return normalized.substring(0, 300);
    }
}
