package com.salmon.studion.domain.clip.dto.request;

import com.salmon.studion.global.common.response.ErrorCode;
import com.salmon.studion.global.exception.BusinessException;
import lombok.Getter;
import lombok.NoArgsConstructor;
import lombok.Setter;

@Getter
@Setter
@NoArgsConstructor
public class ClipPasteRequest extends ClipRequest {
    private Integer targetTrackId;
    private Double targetStartBar;

    @Override
    public void validate() {
        if (getProjectId() == null || targetTrackId == null || targetStartBar == null)
            throw new BusinessException(ErrorCode.INVALID_REQUEST);
    }
}
