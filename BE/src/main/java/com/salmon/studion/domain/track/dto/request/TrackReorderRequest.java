package com.salmon.studion.domain.track.dto.request;

import com.salmon.studion.global.common.response.ErrorCode;
import com.salmon.studion.global.exception.BusinessException;
import lombok.Getter;
import lombok.NoArgsConstructor;
import lombok.Setter;

@Getter
@Setter
@NoArgsConstructor
public class TrackReorderRequest extends TrackRequest{
    private Integer trackId;
    private Integer preTrackId;
    private Integer postTrackId;

    @Override
    public void validate() {
        if(getProjectId() == null || trackId == null)
            throw new BusinessException(ErrorCode.INVALID_REQUEST);

        if(trackId.equals(preTrackId) || trackId.equals(postTrackId))
            throw new BusinessException(ErrorCode.INVALID_REQUEST);
    }
}
