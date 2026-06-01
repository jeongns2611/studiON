package com.salmon.studion.domain.clip.dto.request;

import com.salmon.studion.global.common.enums.MimeType;
import com.salmon.studion.global.common.response.ErrorCode;
import com.salmon.studion.global.exception.BusinessException;
import lombok.Getter;
import lombok.NoArgsConstructor;
import lombok.Setter;

@Getter
@Setter
@NoArgsConstructor
public class ClipCreateRequest extends ClipRequest {
    private Integer trackId;
    private Double startBar;
    private String color;
    private String objectKey;
    private String originalName;
    private String storedName;
    private MimeType mimeType;
    private Integer sizeBytes;
    private Integer durationMs;

    @Override
    public void validate() {
        if (getProjectId() == null || trackId == null || startBar == null || color == null
                || objectKey == null || originalName == null || storedName == null
                || mimeType == null || sizeBytes == null || durationMs == null)
            throw new BusinessException(ErrorCode.INVALID_REQUEST);
    }
}
