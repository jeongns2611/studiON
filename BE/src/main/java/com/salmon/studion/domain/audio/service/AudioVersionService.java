package com.salmon.studion.domain.audio.service;

import com.salmon.studion.domain.audio.dto.request.AudioVersionCreateRequest;
import com.salmon.studion.domain.audio.dto.request.AudioVersionUploadedCreateRequest;
import com.salmon.studion.domain.audio.dto.response.AudioVersionCreateResponse;
import com.salmon.studion.domain.audio.dto.response.AudioVersionDeleteResponse;
import com.salmon.studion.domain.audio.dto.response.AudioVersionDownloadUrlResponse;
import com.salmon.studion.domain.audio.dto.response.AudioVersionListResponse;
import com.salmon.studion.domain.audio.entity.AudioMetadata;
import com.salmon.studion.domain.audio.entity.ProjectMasterAudioVersion;
import com.salmon.studion.domain.audio.render.AudioVersionRenderSnapshotSerializer;
import com.salmon.studion.domain.audio.render.AudioVersionRenderSnapshotService;
import com.salmon.studion.domain.audio.render.dto.AudioVersionRenderSnapshot;
import com.salmon.studion.domain.audio.repository.AudioMetadataRepository;
import com.salmon.studion.domain.audio.repository.AudioVersionRepository;
import com.salmon.studion.domain.project.entity.Project;
import com.salmon.studion.domain.project.service.ProjectService;
import com.salmon.studion.global.common.enums.AudioVersionStatus;
import com.salmon.studion.global.common.response.ErrorCode;
import com.salmon.studion.global.exception.BusinessException;
import com.salmon.studion.global.infrastructure.s3.S3StorageService;
import com.salmon.studion.global.infrastructure.s3.dto.DownloadPresignedUrlResult;
import lombok.RequiredArgsConstructor;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

import java.util.List;

@Service
@RequiredArgsConstructor
public class AudioVersionService {

    private final AudioVersionRepository audioVersionRepository;
    private final AudioMetadataRepository audioMetadataRepository;
    private final ProjectService projectService;
    private final AudioVersionRenderSnapshotService audioVersionRenderSnapshotService;
    private final AudioVersionRenderSnapshotSerializer audioVersionRenderSnapshotSerializer;
    private final S3StorageService s3StorageService;

    public AudioVersionCreateResponse createAudioVersion(
            Integer projectId,
            AudioVersionCreateRequest request,
            Integer userId
    ) {
        Project project = projectService.getProjectOrThrow(projectId);
        AudioVersionRenderSnapshot snapshot = audioVersionRenderSnapshotService.createSnapshot(projectId, userId);
        String snapshotJson = audioVersionRenderSnapshotSerializer.serialize(snapshot);

        ProjectMasterAudioVersion audioVersion = audioVersionRepository.saveAndFlush(
                ProjectMasterAudioVersion.createProcessing(
                        project,
                        request.getName(),
                        request.getMemo(),
                        snapshotJson
                )
        );

        return new AudioVersionCreateResponse(
                audioVersion.getId(),
                audioVersion.getName(),
                audioVersion.getStatus(),
                audioVersion.getCreatedAt()
        );
    }

    @Transactional
    public AudioVersionCreateResponse createUploadedAudioVersion(
            Integer projectId,
            AudioVersionUploadedCreateRequest request,
            AudioMetadata audioMetadata
    ) {
        Project project = projectService.getProjectOrThrow(projectId);

        ProjectMasterAudioVersion audioVersion = audioVersionRepository.saveAndFlush(
                ProjectMasterAudioVersion.createReady(
                        project,
                        request.getName(),
                        request.getMemo(),
                        audioMetadata
                )
        );

        return new AudioVersionCreateResponse(
                audioVersion.getId(),
                audioVersion.getName(),
                audioVersion.getStatus(),
                audioVersion.getCreatedAt()
        );
    }

    @Transactional(readOnly = true)
    public AudioVersionListResponse getAudioVersionList(Integer projectId) {
        List<ProjectMasterAudioVersion> audioVersions =
                audioVersionRepository.findAllByProjectIdAndStatusReady(projectId, AudioVersionStatus.READY);

        List<AudioVersionListResponse.AudioVersionSummary> versions = audioVersions.stream()
                .map(audioVersion -> new AudioVersionListResponse.AudioVersionSummary(
                        audioVersion.getId(),
                        audioVersion.getName(),
                        audioVersion.getMemo(),
                        audioVersion.getAudioMetadata().getDurationMs(),
                        audioVersion.getAudioMetadata().getSizeBytes(),
                        audioVersion.getCreatedAt()
                ))
                .toList();

        return new AudioVersionListResponse(versions.size(), versions);
    }

    @Transactional(readOnly = true)
    public AudioVersionDownloadUrlResponse getAudioVersionDownloadUrl(Integer projectId, Integer versionId) {
        ProjectMasterAudioVersion audioVersion = audioVersionRepository.findByIdAndProjectIdWithAudioMetadata(versionId, projectId)
                .orElseThrow(() -> new BusinessException(ErrorCode.AUDIO_VERSION_NOT_FOUND));

        if (audioVersion.getStatus() != AudioVersionStatus.READY || audioVersion.getAudioMetadata() == null) {
            throw new BusinessException(ErrorCode.AUDIO_VERSION_NOT_FOUND);
        }

        AudioMetadata audioMetadata = audioVersion.getAudioMetadata();
        DownloadPresignedUrlResult result = s3StorageService.createDownloadUrl(
                audioMetadata.getObjectKey(),
                audioMetadata.getOriginalName()
        );

        return new AudioVersionDownloadUrlResponse(
                versionId,
                result.getDownloadUrl(),
                result.getExpiresAt()
        );
    }

    @Transactional
    public AudioVersionDeleteResponse deleteAudioVersion(Integer projectId, Integer versionId) {
        ProjectMasterAudioVersion audioVersion = audioVersionRepository.findByIdAndProjectIdWithAudioMetadata(versionId, projectId)
                .orElseThrow(() -> new BusinessException(ErrorCode.AUDIO_VERSION_NOT_FOUND));

        AudioMetadata audioMetadata = audioVersion.getAudioMetadata();

        audioVersionRepository.delete(audioVersion);
        if (audioMetadata != null) {
            audioMetadataRepository.delete(audioMetadata);
        }

        return new AudioVersionDeleteResponse(versionId, true);
    }

    @Transactional(readOnly = true)
    public ProjectMasterAudioVersion getAudioVersionOrThrow(Integer versionId) {
        return audioVersionRepository.findByIdWithProjectAndAudioMetadata(versionId)
                .orElseThrow(() -> new BusinessException(ErrorCode.AUDIO_VERSION_NOT_FOUND));
    }

    @Transactional
    public void markReady(Integer versionId, AudioMetadata audioMetadata) {
        ProjectMasterAudioVersion audioVersion = audioVersionRepository.findById(versionId)
                .orElseThrow(() -> new BusinessException(ErrorCode.AUDIO_VERSION_NOT_FOUND));
        audioVersion.markReady(audioMetadata);
    }

    @Transactional
    public void markFailed(Integer versionId, String failedReason) {
        ProjectMasterAudioVersion audioVersion = audioVersionRepository.findById(versionId)
                .orElseThrow(() -> new BusinessException(ErrorCode.AUDIO_VERSION_NOT_FOUND));
        audioVersion.markFailed(failedReason);
    }
}
