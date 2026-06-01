package com.salmon.studion.domain.clip.dto.request;

import com.salmon.studion.global.common.response.ErrorCode;
import com.salmon.studion.global.exception.BusinessException;
import lombok.Getter;
import lombok.NoArgsConstructor;
import lombok.Setter;

@Getter
@Setter
@NoArgsConstructor
public class ClipMoveRequest extends ClipRequest {
    private Integer clipId;
    private Integer targetTrackId;
    private Double targetStartBar;

    @Override
    public void validate() {
        if (getProjectId() == null || clipId == null || targetTrackId == null || targetStartBar == null)
            throw new BusinessException(ErrorCode.INVALID_REQUEST);
    }
}
