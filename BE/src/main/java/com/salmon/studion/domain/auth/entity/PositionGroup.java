package com.salmon.studion.domain.auth.entity;

import com.salmon.studion.global.common.entity.BaseEntity;
import jakarta.persistence.*;
import lombok.AccessLevel;
import lombok.Getter;
import lombok.NoArgsConstructor;

@Table(name = "position_group")
@Entity
@Getter
@NoArgsConstructor(access = AccessLevel.PROTECTED)
public class PositionGroup extends BaseEntity {

    @Id
    private Integer code;

    @Column(nullable = false, length = 50)
    private String name;

    @Column(name = "`order`", nullable = false)
    private Integer order;
}
