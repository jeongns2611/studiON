package com.salmon.studion.domain.auth.entity;

import com.salmon.studion.global.common.entity.BaseEntity;
import com.salmon.studion.global.common.enums.UserRole;
import jakarta.persistence.*;
import lombok.AccessLevel;
import lombok.Builder;
import lombok.Getter;
import lombok.NoArgsConstructor;
import org.hibernate.annotations.SQLDelete;
import org.hibernate.annotations.SQLRestriction;

import java.time.Instant;

@Table(name = "user")
@Entity
@Getter
@NoArgsConstructor(access = AccessLevel.PROTECTED)
@SQLDelete(sql = "update user set deleted_at = now() where id = ?")
@SQLRestriction("deleted_at is null")
public class User extends BaseEntity {

    @Id
    @GeneratedValue(strategy = GenerationType.IDENTITY)
    private Integer id;

    @Column(nullable = false, length = 255)
    private String email;

    @Column(nullable = false, length = 20)
    private String provider;

    @Column(nullable = false, length = 100)
    private String providerId;

    @Column(nullable = true, length = 255)
    private String profileImgUrl;

    @Column(nullable = false, length = 20)
    private String nickname;

    @Enumerated(EnumType.STRING)
    @Column(nullable = false, length = 20)
    private UserRole role = UserRole.BASIC;

    @Column(nullable = false)
    private Instant lastLoginAt;

    @Column(nullable = true)
    private Instant deletedAt;

    @Builder
    private User(String email, String provider, String providerId, String profileImgUrl, String nickname, Instant lastLoginAt) {
        this.email = email;
        this.provider = provider;
        this.providerId = providerId;
        this.profileImgUrl = profileImgUrl;
        this.nickname = nickname;
        this.role = UserRole.BASIC;
        this.lastLoginAt = lastLoginAt;
    }

    //마지막 로그인 일자 갱신
    public void updateLastLoginAt(Instant lastLoginAt){
        this.lastLoginAt = lastLoginAt;
    }

    //닉네임 변경(db조회 중복검사 로직 추후 추가하기)
    public void updateNickname(String nickname){
        this.nickname = nickname;
    }
}

