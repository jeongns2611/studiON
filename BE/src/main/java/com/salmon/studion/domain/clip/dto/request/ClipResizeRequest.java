package com.salmon.studion.domain.clip.dto.request;

import com.salmon.studion.global.common.response.ErrorCode;
import com.salmon.studion.global.exception.BusinessException;
import lombok.Getter;
import lombok.NoArgsConstructor;
import lombok.Setter;

@Getter
@Setter
@NoArgsConstructor
public class ClipResizeRequest extends ClipRequest {
    private Integer clipId;
    private Double startBar;
    private Double length;

    @Override
    public void validate() {
        if (getProjectId() == null || clipId == null || startBar == null || length == null)
            throw new BusinessException(ErrorCode.INVALID_REQUEST);
    }
}
