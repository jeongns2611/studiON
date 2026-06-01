package com.salmon.studion.domain.audio.render;

import com.salmon.studion.domain.audio.entity.AudioMetadata;
import com.salmon.studion.domain.audio.entity.ProjectMasterAudioVersion;
import com.salmon.studion.domain.audio.render.dto.AudioVersionRenderResult;
import com.salmon.studion.domain.audio.render.dto.AudioVersionRenderSnapshot;
import com.salmon.studion.domain.audio.service.AudioVersionService;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.scheduling.annotation.Async;
import org.springframework.stereotype.Component;

import java.nio.file.Path;

@Slf4j
@Component
@RequiredArgsConstructor
public class AudioVersionRenderWorker {

    private final AudioVersionService audioVersionService;
    private final AudioVersionRenderSnapshotSerializer audioVersionRenderSnapshotSerializer;
    private final AudioVersionRenderEngine audioVersionRenderEngine;
    private final AudioVersionRenderStorageService audioVersionRenderStorageService;

    @Async
    public void renderAsync(Integer versionId) {
        Path workingDirectory = null;

        try {
            ProjectMasterAudioVersion audioVersion = audioVersionService.getAudioVersionOrThrow(versionId);
            AudioVersionRenderSnapshot snapshot = audioVersionRenderSnapshotSerializer.deserialize(
                    audioVersion.getRenderSnapshotJson()
            );

            AudioVersionRenderResult renderResult = audioVersionRenderEngine.render(snapshot, audioVersion.getName());
            workingDirectory = renderResult.getOutputPath().getParent();

            AudioMetadata audioMetadata = audioVersionRenderStorageService.storeRenderedAudio(
                    snapshot.getProjectId(),
                    renderResult
            );
            audioVersionService.markReady(versionId, audioMetadata);
        } catch (Exception exception) {
            log.error("[오디오 버전 렌더 실패] versionId={}", versionId, exception);
            try {
                audioVersionService.markFailed(versionId, trimFailureReason(exception.getMessage()));
            } catch (Exception ignored) {
                log.error("[오디오 버전 실패 상태 반영 실패] versionId={}", versionId, ignored);
            }
        } finally {
            audioVersionRenderEngine.cleanupWorkingDirectory(workingDirectory);
        }
    }

    private String trimFailureReason(String message) {
        if (message == null || message.isBlank()) {
            return "오디오 버전 렌더링에 실패했습니다.";
        }
        return message.length() <= 1000 ? message : message.substring(0, 1000);
    }
}
