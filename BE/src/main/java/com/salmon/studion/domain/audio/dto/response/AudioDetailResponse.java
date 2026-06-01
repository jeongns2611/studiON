package com.salmon.studion.domain.audio.dto.response;

import com.salmon.studion.domain.audio.entity.AudioMetadata;
import com.salmon.studion.global.common.enums.MimeType;
import lombok.AccessLevel;
import lombok.AllArgsConstructor;
import lombok.Getter;

@Getter
@AllArgsConstructor(access = AccessLevel.PRIVATE)
public class AudioDetailResponse {

    private Integer audioMetadataId;
    private String originalName;
    private MimeType mimeType;
    private Integer sizeBytes;
    private Integer durationMs;
    private String audioUrl;

    public static AudioDetailResponse of(
            AudioMetadata audioMetadata,
            String audioUrl
    ) {
        return new AudioDetailResponse(
                audioMetadata.getId(),
                audioMetadata.getOriginalName(),
                audioMetadata.getMimeType(),
                audioMetadata.getSizeBytes(),
                audioMetadata.getDurationMs(),
                audioUrl
        );
    }
}
