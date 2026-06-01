package com.salmon.studion.domain.audio.facade;

import com.salmon.studion.domain.audio.dto.request.AudioListRequest;
import com.salmon.studion.domain.audio.dto.request.AudioMetadataCreateRequest;
import com.salmon.studion.domain.audio.dto.request.AudioUploadUrlRequest;
import com.salmon.studion.domain.audio.dto.response.AudioDetailResponse;
import com.salmon.studion.domain.audio.dto.response.AudioListResponse;
import com.salmon.studion.domain.audio.dto.response.AudioMetadataCreateResponse;
import com.salmon.studion.domain.audio.dto.response.AudioUploadUrlResponse;
import com.salmon.studion.domain.audio.entity.AudioMetadata;
import com.salmon.studion.domain.audio.service.AudioService;
import com.salmon.studion.domain.audio.service.AudioUploadLimitService;
import com.salmon.studion.domain.auth.entity.User;
import com.salmon.studion.domain.auth.service.UserService;
import com.salmon.studion.domain.clip.entity.Clip;
import com.salmon.studion.domain.project.service.ProjectMemberService;
import com.salmon.studion.global.common.response.ErrorCode;
import com.salmon.studion.global.exception.BusinessException;
import com.salmon.studion.global.infrastructure.cdn.CdnUrlService;
import com.salmon.studion.global.infrastructure.s3.S3StorageService;
import com.salmon.studion.global.infrastructure.s3.dto.PresignedUrlResult;
import lombok.RequiredArgsConstructor;
import org.springframework.stereotype.Component;

import java.util.List;

@Component
@RequiredArgsConstructor
public class AudioFacade {

    private final AudioService audioService;
    private final UserService userService;
    private final S3StorageService s3StorageService;
    private final CdnUrlService cdnUrlService;
    private final ProjectMemberService projectMemberService;
    private final AudioUploadLimitService audioUploadLimitService;

    public AudioUploadUrlResponse getAudioUploadUrl(Integer projectId, AudioUploadUrlRequest audioUploadUrlRequest, Integer userId) {
        projectMemberService.validateProjectMember(projectId, userId);

        User user = userService.getUserByUserId(userId);
        validateAudioUploadLimit(user, audioUploadUrlRequest.getSizeBytes());

        audioService.validateMimeTypeAndExtension(audioUploadUrlRequest.getOriginalName(), audioUploadUrlRequest.getMimeType());

        PresignedUrlResult result = s3StorageService.createUploadUrl(
                projectId,
                audioUploadUrlRequest.getOriginalName(),
                audioUploadUrlRequest.getMimeType().getValue(),
                audioUploadUrlRequest.getSizeBytes()
        );

        return AudioUploadUrlResponse.of(result.getObjectKey(), result.getStoredName(), result.getUploadUrl());
    }

    public AudioMetadataCreateResponse createAudioMetadata(Integer projectId, AudioMetadataCreateRequest request, Integer userId) {
        projectMemberService.validateProjectMember(projectId, userId);

        User user = userService.getUserByUserId(userId);
        validateAudioUploadLimit(user, request.getSizeBytes());

        audioService.validateMimeTypeAndExtension(request.getOriginalName(), request.getMimeType());
        audioService.validateObjectKey(projectId, request.getObjectKey());
        audioService.validateStoredName(request.getObjectKey(), request.getStoredName());

        s3StorageService.validateUploadedObject(request.getObjectKey(), request.getSizeBytes(), request.getMimeType().getValue());

        AudioMetadata audioMetadata = audioService.createAudioMetadata(request);
        return AudioMetadataCreateResponse.from(audioMetadata);
    }

    public AudioDetailResponse getAudioDetail(Integer projectId, Integer audioMetadataId, Integer userId) {
        projectMemberService.validateProjectMember(projectId, userId);

        AudioMetadata audioMetadata = audioService.getAudioMetadata(audioMetadataId);
        audioService.validateObjectKey(projectId, audioMetadata.getObjectKey());

        String audioUrl = cdnUrlService.createAudioUrl(audioMetadata.getObjectKey());
        return AudioDetailResponse.of(audioMetadata, audioUrl);
    }

    public AudioListResponse getAudiosForClips(Integer projectId, AudioListRequest audioListRequest, Integer userId) {
        projectMemberService.validateProjectMember(projectId, userId);

        List<Clip> clips = audioService.getClipsWithAudioMetadata(projectId, audioListRequest.getClipIds());

        List<AudioListResponse.AudioListItemResponse> audios = clips.stream()
                .map(clip -> {
                    AudioMetadata audioMetadata = clip.getAudioMetadata();
                    String audioUrl = cdnUrlService.createAudioUrl(audioMetadata.getObjectKey());
                    return AudioListResponse.AudioListItemResponse.of(clip.getId(), audioMetadata, audioUrl);
                })
                .toList();

        return AudioListResponse.of(audios);
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
