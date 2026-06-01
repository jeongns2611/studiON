package com.salmon.studion.domain.comment.dto.websocket;

import com.salmon.studion.global.common.response.ErrorCode;
import com.salmon.studion.global.exception.BusinessException;
import lombok.Getter;
import lombok.NoArgsConstructor;

import java.math.BigDecimal;
import java.util.List;

@Getter
@NoArgsConstructor
public class CommentCreateRequest extends CommentRequest {

    private Integer trackId;
    private Integer parentCommentId;
    private String content;
    private BigDecimal location;    // 댓글이 달린 마디 위치
    private List<Integer> mentionedUserIds;

    @Override
    public void validate() {
        if (getProjectId() == null || trackId == null || content == null || location == null) {
            throw new BusinessException(ErrorCode.INVALID_REQUEST);
        }
    }
}
