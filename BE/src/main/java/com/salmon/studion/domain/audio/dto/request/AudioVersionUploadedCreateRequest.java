package com.salmon.studion.domain.audio.dto.request;

import com.salmon.studion.global.common.enums.MimeType;
import jakarta.validation.constraints.NotBlank;
import jakarta.validation.constraints.NotNull;
import jakarta.validation.constraints.Positive;
import jakarta.validation.constraints.Size;
import lombok.Getter;
import lombok.NoArgsConstructor;

@Getter
@NoArgsConstructor
public class AudioVersionUploadedCreateRequest {

    @NotBlank(message = "프로젝트 버전 이름은 필수입니다.")
    @Size(max = AudioVersionCreateRequest.MAX_AUDIO_VERSION_NAME, message = "프로젝트 버전 이름은 50자를 초과할 수 없습니다.")
    private String name;

    @Size(max = AudioVersionCreateRequest.MAX_AUDIO_VERSION_MEMO, message = "프로젝트 버전에 대한 설명은 255자를 초과할 수 없습니다.")
    private String memo;

    @NotBlank(message = "S3 objectKey는 필수입니다.")
    private String objectKey;

    @NotBlank(message = "원본 파일명은 필수입니다.")
    private String originalName;

    @NotBlank(message = "저장 파일명은 필수입니다.")
    private String storedName;

    @NotNull(message = "파일 MIME 타입은 필수입니다.")
    private MimeType mimeType;

    @NotNull(message = "파일 크기는 필수입니다.")
    @Positive(message = "파일 크기는 0보다 커야 합니다.")
    private Integer sizeBytes;

    @NotNull(message = "오디오 길이는 필수입니다.")
    @Positive(message = "오디오 길이는 0보다 커야 합니다.")
    private Integer durationMs;

    public AudioMetadataCreateRequest toAudioMetadataCreateRequest() {
        return AudioMetadataCreateRequest.builder()
                .objectKey(objectKey)
                .originalName(originalName)
                .storedName(storedName)
                .mimeType(mimeType)
                .sizeBytes(sizeBytes)
                .durationMs(durationMs)
                .build();
    }
}
