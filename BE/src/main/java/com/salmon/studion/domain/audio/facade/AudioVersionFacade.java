package com.salmon.studion.domain.audio.facade;

import com.salmon.studion.domain.audio.dto.request.AudioMetadataCreateRequest;
import com.salmon.studion.domain.audio.dto.request.AudioUploadUrlRequest;
import com.salmon.studion.domain.audio.dto.request.AudioVersionCreateRequest;
import com.salmon.studion.domain.audio.dto.request.AudioVersionUploadedCreateRequest;
import com.salmon.studion.domain.audio.dto.response.AudioVersionCreateResponse;
import com.salmon.studion.domain.audio.dto.response.AudioVersionDeleteResponse;
import com.salmon.studion.domain.audio.dto.response.AudioVersionDownloadUrlResponse;
import com.salmon.studion.domain.audio.dto.response.AudioVersionListResponse;
import com.salmon.studion.domain.audio.dto.response.AudioVersionUploadUrlResponse;
import com.salmon.studion.domain.audio.entity.AudioMetadata;
import com.salmon.studion.domain.audio.render.AudioVersionRenderWorker;
import com.salmon.studion.domain.audio.service.AudioService;
import com.salmon.studion.domain.audio.service.AudioUploadLimitService;
import com.salmon.studion.domain.audio.service.AudioVersionService;
import com.salmon.studion.domain.auth.entity.User;
import com.salmon.studion.domain.auth.service.UserService;
import com.salmon.studion.domain.project.service.ProjectMemberService;
import com.salmon.studion.global.common.response.ErrorCode;
import com.salmon.studion.global.exception.BusinessException;
import com.salmon.studion.global.infrastructure.s3.S3StorageService;
import com.salmon.studion.global.infrastructure.s3.dto.PresignedUrlResult;
import lombok.RequiredArgsConstructor;
import org.springframework.stereotype.Component;

@Component
@RequiredArgsConstructor
public class AudioVersionFacade {

    private final UserService userService;
    private final ProjectMemberService projectMemberService;
    private final AudioVersionService audioVersionService;
    private final AudioVersionRenderWorker audioVersionRenderWorker;
    private final AudioService audioService;
    private final S3StorageService s3StorageService;
    private final AudioUploadLimitService audioUploadLimitService;

    public AudioVersionCreateResponse createAudioVersion(Integer projectId, AudioVersionCreateRequest request, Integer userId) {
        projectMemberService.validateProjectMember(projectId, userId);

        AudioVersionCreateResponse response = audioVersionService.createAudioVersion(projectId, request, userId);
        audioVersionRenderWorker.renderAsync(response.getVersionId());
        return response;
    }

    public AudioVersionUploadUrlResponse getAudioVersionUploadUrl(
            Integer projectId,
            AudioUploadUrlRequest request,
            Integer userId
    ) {
        projectMemberService.validateProjectMember(projectId, userId);

        User user = userService.getUserByUserId(userId);
        validateAudioUploadLimit(user, request.getSizeBytes());

        audioService.validateMimeTypeAndExtension(request.getOriginalName(), request.getMimeType());

        PresignedUrlResult result = s3StorageService.createUploadUrl(
                projectId,
                request.getOriginalName(),
                request.getMimeType().getValue(),
                request.getSizeBytes()
        );

        return new AudioVersionUploadUrlResponse(
                result.getObjectKey(),
                result.getStoredName(),
                result.getUploadUrl()
        );
    }

    public AudioVersionCreateResponse createUploadedAudioVersion(
            Integer projectId,
            AudioVersionUploadedCreateRequest request,
            Integer userId
    ) {
        projectMemberService.validateProjectMember(projectId, userId);

        User user = userService.getUserByUserId(userId);
        validateAudioUploadLimit(user, request.getSizeBytes());

        AudioMetadataCreateRequest metadataRequest = request.toAudioMetadataCreateRequest();
        audioService.validateMimeTypeAndExtension(metadataRequest.getOriginalName(), metadataRequest.getMimeType());
        audioService.validateObjectKey(projectId, metadataRequest.getObjectKey());
        audioService.validateStoredName(metadataRequest.getObjectKey(), metadataRequest.getStoredName());
        s3StorageService.validateUploadedObject(
                metadataRequest.getObjectKey(),
                metadataRequest.getSizeBytes(),
                metadataRequest.getMimeType().getValue()
        );

        AudioMetadata audioMetadata = audioService.createAudioMetadata(metadataRequest);
        return audioVersionService.createUploadedAudioVersion(projectId, request, audioMetadata);
    }

    public AudioVersionListResponse getAudioVersionList(Integer projectId, Integer userId) {
        projectMemberService.validateProjectMember(projectId, userId);

        return audioVersionService.getAudioVersionList(projectId);
    }

    public AudioVersionDownloadUrlResponse getAudioVersionDownloadUrl(Integer projectId, Integer versionId, Integer userId) {
        projectMemberService.validateProjectMember(projectId, userId);

        return audioVersionService.getAudioVersionDownloadUrl(projectId, versionId);
    }

    public AudioVersionDeleteResponse deleteAudioVersion(Integer projectId, Integer versionId, Integer userId) {
        projectMemberService.validateProjectMember(projectId, userId);

        return audioVersionService.deleteAudioVersion(projectId, versionId);
    }

    private void validateAudioUploadLimit(User user, Integer requestedSizeBytes) {
        AudioUploadLimitService.AudioUploadLimit limit = audioUploadLimitService.getLimit(user.getRole());

        if (requestedSizeBytes > limit.maxFileSizeBytes()) {
            throw new BusinessException(
                    ErrorCode.FAIL,
                    "현재 사용자에게 허용된 단일 오디오 업로드 용량을 초과했습니다."
            );
        }

        long currentTotalSizeBytes = audioService.sumSizeBytesByCreatedBy(user.getId());
        long nextTotalSizeBytes = currentTotalSizeBytes + requestedSizeBytes.longValue();

        if (nextTotalSizeBytes > limit.maxTotalSizeBytes()) {
            throw new BusinessException(
                    ErrorCode.FAIL,
                    "현재 사용자에게 허용된 전체 오디오 업로드 용량을 초과했습니다."
            );
        }
    }
}
