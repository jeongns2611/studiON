package com.salmon.studion.domain.audio.dto.response;

import com.salmon.studion.domain.audio.entity.AudioMetadata;
import com.salmon.studion.global.common.enums.MimeType;
import lombok.AccessLevel;
import lombok.AllArgsConstructor;
import lombok.Getter;

import java.util.List;

@Getter
@AllArgsConstructor(access = AccessLevel.PRIVATE)
public class AudioListResponse {

    private List<AudioListItemResponse> audios;

    public static AudioListResponse of(List<AudioListItemResponse> audios) {
        return new AudioListResponse(audios);
    }

    public record AudioListItemResponse(
            Integer clipId,
            Integer audioMetadataId,
            String originalName,
            MimeType mimeType,
            Integer sizeBytes,
            Integer durationMs,
            String audioUrl
    ) {
        public static AudioListItemResponse of(Integer clipId, AudioMetadata audioMetadata, String audioUrl) {
            return new AudioListItemResponse(
                    clipId,
                    audioMetadata.getId(),
                    audioMetadata.getOriginalName(),
                    audioMetadata.getMimeType(),
                    audioMetadata.getSizeBytes(),
                    audioMetadata.getDurationMs(),
                    audioUrl
            );
        }
    }
}