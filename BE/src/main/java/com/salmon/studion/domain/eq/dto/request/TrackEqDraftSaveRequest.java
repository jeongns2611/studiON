package com.salmon.studion.domain.eq.dto.request;

import com.salmon.studion.global.common.response.ErrorCode;
import com.salmon.studion.global.exception.BusinessException;
import lombok.Getter;
import lombok.NoArgsConstructor;
import lombok.Setter;

import java.util.List;

@Getter
@Setter
@NoArgsConstructor
public class TrackEqDraftSaveRequest extends TrackEqRequest {

    private Integer trackEqId;
    private List<BandRequest> bands;

    @Override
    public void validate() {
        if (getProjectId() == null || trackEqId == null || bands == null) {
            throw new BusinessException(ErrorCode.INVALID_REQUEST);
        }
    }
}
