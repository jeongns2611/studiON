package com.salmon.studion.domain.clip.dto.request;

import com.salmon.studion.global.common.response.ErrorCode;
import com.salmon.studion.global.exception.BusinessException;
import lombok.Getter;
import lombok.NoArgsConstructor;
import lombok.Setter;

@Getter
@Setter
@NoArgsConstructor
public class ClipSplitRequest extends ClipRequest {
    private Integer clipId;
    private Double splitBar;

    @Override
    public void validate() {
        if (getProjectId() == null || clipId == null || splitBar == null)
            throw new BusinessException(ErrorCode.INVALID_REQUEST);
    }
}
