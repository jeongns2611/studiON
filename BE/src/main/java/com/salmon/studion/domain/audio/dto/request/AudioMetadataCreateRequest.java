package com.salmon.studion.domain.audio.dto.request;

import com.salmon.studion.global.common.enums.MimeType;
import jakarta.validation.constraints.NotBlank;
import jakarta.validation.constraints.NotNull;
import jakarta.validation.constraints.Positive;
import lombok.AllArgsConstructor;
import lombok.Builder;
import lombok.Getter;
import lombok.NoArgsConstructor;

@Builder
@Getter
@NoArgsConstructor
@AllArgsConstructor(access = lombok.AccessLevel.PRIVATE)
public class AudioMetadataCreateRequest {

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
}