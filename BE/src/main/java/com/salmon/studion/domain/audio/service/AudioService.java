package com.salmon.studion.domain.audio.service;

import com.salmon.studion.domain.audio.dto.request.AudioMetadataCreateRequest;
import com.salmon.studion.domain.audio.entity.AudioMetadata;
import com.salmon.studion.domain.audio.repository.AudioMetadataRepository;
import com.salmon.studion.domain.clip.entity.Clip;
import com.salmon.studion.domain.clip.repository.ClipRepository;
import com.salmon.studion.global.common.enums.MimeType;
import com.salmon.studion.global.common.response.ErrorCode;
import com.salmon.studion.global.exception.BusinessException;
import lombok.RequiredArgsConstructor;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

import java.util.List;
import java.util.Set;
import java.util.stream.Collectors;

@Service
@RequiredArgsConstructor
public class AudioService {

    private final AudioMetadataRepository audioMetadataRepository;
    private final ClipRepository clipRepository;

    @Transactional
    public AudioMetadata createAudioMetadata(AudioMetadataCreateRequest request) {
        AudioMetadata audioMetadata = AudioMetadata.create(
                request.getObjectKey(),
                request.getOriginalName(),
                request.getStoredName(),
                request.getMimeType(),
                request.getSizeBytes(),
                request.getDurationMs()
        );

        return audioMetadataRepository.save(audioMetadata);
    }

    @Transactional(readOnly = true)
    public AudioMetadata getAudioMetadata(Integer audioMetadataId) {
        return audioMetadataRepository.findById(audioMetadataId)
                .orElseThrow(() -> new BusinessException(ErrorCode.AUDIO_METADATA_NOT_FOUND));
    }

    public void validateMimeTypeAndExtension(String originalName, MimeType mimeType) {
        int dotIndex = originalName.lastIndexOf('.');
        if (dotIndex == -1 || dotIndex == originalName.length() - 1) {
            throw new BusinessException(ErrorCode.AUDIO_INVALID_FORMAT);
        }

        String extension = originalName.substring(dotIndex + 1).toLowerCase();

        if (!mimeType.matchesExtension(extension)) {
            throw new BusinessException(ErrorCode.AUDIO_INVALID_FORMAT);
        }
    }

    public void validateObjectKey(Integer projectId, String objectKey) {
        String expectedPrefix = "projects/" + projectId + "/audios/";

        if (!objectKey.startsWith(expectedPrefix)) {
            throw new BusinessException(ErrorCode.AUDIO_INVALID_PROJECT_SCOPE);
        }
    }

    public void validateStoredName(String objectKey, String storedName) {
        if (!objectKey.endsWith("/" + storedName)) {
            throw new BusinessException(ErrorCode.AUDIO_OBJECT_KEY_MISMATCH);
        }
    }

    public List<Clip> getClipsWithAudioMetadata(Integer projectId, List<Integer> clipIds) {
        List<Clip> clips = clipRepository.findAllByIdsAndProjectIdWithAudioMetadata(clipIds, projectId);

        validateAllClipsFound(clipIds, clips);

        return clips;
    }

    public long sumSizeBytesByCreatedBy(Integer userId) {
        return audioMetadataRepository.sumSizeBytesByCreatedBy(userId);
    }

    private void validateAllClipsFound(List<Integer> requestClipIds, List<Clip> foundClips) {
        Set<Integer> foundClipIds = foundClips.stream().map(Clip::getId).collect(Collectors.toSet());

        boolean hasMissingClip = requestClipIds.stream().anyMatch(clipId -> !foundClipIds.contains(clipId));

        if (hasMissingClip) {
            throw new BusinessException(ErrorCode.CLIP_NOT_FOUND);
        }
    }
}
