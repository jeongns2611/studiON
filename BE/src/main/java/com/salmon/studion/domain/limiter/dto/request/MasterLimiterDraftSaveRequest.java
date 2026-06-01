package com.salmon.studion.domain.limiter.dto.request;

import com.salmon.studion.global.common.response.ErrorCode;
import com.salmon.studion.global.exception.BusinessException;
import lombok.Getter;
import lombok.NoArgsConstructor;
import lombok.Setter;

@Getter
@Setter
@NoArgsConstructor
public class MasterLimiterDraftSaveRequest extends MasterLimiterRequest {

    private Boolean isEnabled;
    private Double thresholdDb;
    private Double ceilingDbfs;
    private Double attackMs;
    private Double releaseMs;
    private Double inputGainDb;
    private Double makeupGainDb;
    private Integer jobId;
    private Integer suggestionActionId;
    private Integer appliedSuggestionId;
    private String sourceType;

    @Override
    public void validate() {
        if (getProjectId() == null || sourceType == null) {
            throw new BusinessException(ErrorCode.INVALID_REQUEST);
        }
    }
}
